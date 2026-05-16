import random
from decimal import Decimal
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified
from app.modules.games.infrastructure.models import PokerTable
from app.modules.games.blackjack.service import get_deck # Reusamos la baraja estandar
from app.modules.games.poker.evaluator import evaluate_hand, format_hand_name
from app.modules.users.infrastructure.models import User
from app.modules.wallet.infrastructure.models import Transaction

def default_poker_player(user_id: int, username: str) -> dict:
    return {
        "user_id": user_id,
        "username": username,
        "balance_in_play": 0, # Chips at the table
        "round_bet": 0, # Bet in the current betting round
        "hand": [],
        "status": "WAITING", # WAITING, ACTIVE, FOLDED, ALL_IN
        "acted_this_round": False,
        "best_hand_name": "",
        "best_hand_rank": -1
    }

async def get_poker_state(db: AsyncSession, table_id: int) -> dict:
    table = await db.get(PokerTable, table_id)
    if not table:
        return None
            
    return {
        "id": table.id,
        "name": table.name,
        "status": table.status,
        "community_cards": table.community_cards,
        "pot": float(table.pot),
        "current_bet": float(table.current_bet),
        "players": table.players_data,
        "current_turn_index": table.current_turn_index,
        "dealer_button_index": table.dealer_button_index,
        "small_blind": float(table.small_blind),
        "big_blind": float(table.big_blind)
    }

def advance_turn(table: PokerTable, players: List[dict]):
    # Find next active player
    start_idx = table.current_turn_index
    for i in range(1, len(players) + 1):
        idx = (start_idx + i) % len(players)
        if players[idx]["status"] == "ACTIVE":
            table.current_turn_index = idx
            return
            
def check_round_end(table: PokerTable, players: List[dict]) -> bool:
    # A round ends if all active players have acted AND their round_bet matches current_bet (or they are all-in)
    active_players = [p for p in players if p["status"] == "ACTIVE"]
    if len(active_players) <= 1:
        return True # Everyone folded
        
    for p in active_players:
        if not p["acted_this_round"]:
            return False
        if float(p["round_bet"]) < float(table.current_bet) and p["status"] != "ALL_IN":
            return False
    return True

async def next_street(db: AsyncSession, table: PokerTable, players: List[dict]):
    # Move bets to pot
    for p in players:
        table.pot += Decimal(str(p["round_bet"]))
        p["round_bet"] = 0
        p["acted_this_round"] = False
        
    table.current_bet = 0
    
    active_players = [p for p in players if p["status"] in ["ACTIVE", "ALL_IN"]]
    
    if len([p for p in active_players if p["status"] == "ACTIVE"]) <= 1 or table.status == "RIVER":
        # Only 1 person not all-in, or we reached the end -> SHOWDOWN
        if table.status == "PRE_FLOP":
            table.community_cards.extend([table.deck.pop() for _ in range(3)])
            table.status = "FLOP"
        if table.status == "FLOP":
            table.community_cards.append(table.deck.pop())
            table.status = "TURN"
        if table.status == "TURN":
            table.community_cards.append(table.deck.pop())
            table.status = "RIVER"
            
        await resolve_showdown(db, table, players)
        return

    if table.status == "PRE_FLOP":
        table.status = "FLOP"
        table.community_cards.extend([table.deck.pop() for _ in range(3)])
    elif table.status == "FLOP":
        table.status = "TURN"
        table.community_cards.append(table.deck.pop())
    elif table.status == "TURN":
        table.status = "RIVER"
        table.community_cards.append(table.deck.pop())

    # Turn starts at Small Blind
    table.current_turn_index = table.dealer_button_index
    advance_turn(table, players)

async def resolve_showdown(db: AsyncSession, table: PokerTable, players: List[dict]):
    table.status = "SHOWDOWN"
    active_players = [p for p in players if p["status"] in ["ACTIVE", "ALL_IN"]]
    
    if len(active_players) == 1:
        # Everyone folded, this guy wins
        winner = active_players[0]
        winner_payout = table.pot
        winner["balance_in_play"] = float(Decimal(str(winner["balance_in_play"])) + winner_payout)
        table.pot = 0
        return
        
    # Evaluate hands
    best_rank = -1
    best_tiebreaker = []
    winners = []
    
    for p in active_players:
        rank, tiebreaker = evaluate_hand(p["hand"], table.community_cards)
        p["best_hand_rank"] = rank
        p["best_hand_name"] = format_hand_name(rank)
        
        if rank > best_rank:
            best_rank = rank
            best_tiebreaker = tiebreaker
            winners = [p]
        elif rank == best_rank:
            if tiebreaker > best_tiebreaker:
                best_tiebreaker = tiebreaker
                winners = [p]
            elif tiebreaker == best_tiebreaker:
                winners.append(p)
                
    # Split pot
    payout = table.pot / len(winners)
    for w in winners:
        w["balance_in_play"] = float(Decimal(str(w["balance_in_play"])) + payout)
        
    table.pot = 0

async def process_ws_poker_action(db: AsyncSession, table_id: int, user_id: int, action_data: dict) -> dict:
    table = await db.get(PokerTable, table_id)
    if not table:
        return None
        
    action = action_data.get("action")
    players: List[dict] = list(table.players_data) if table.players_data else []
    
    player = next((p for p in players if p["user_id"] == user_id), None)
    
    if action == "join":
        if not player:
            user = await db.get(User, user_id)
            buy_in = Decimal(str(action_data.get("buy_in", 1000)))
            if user.balance >= buy_in:
                user.balance -= buy_in
                tx = Transaction(user_id=user_id, amount=buy_in, transaction_type="BUY_IN", description="Poker Buy In")
                db.add(tx)
                
                new_p = default_poker_player(user_id, user.username if user.username else f"User {user_id}")
                new_p["balance_in_play"] = float(buy_in)
                players.append(new_p)
                
                table.players_data = players
                flag_modified(table, "players_data")
                db.add(table)
                await db.commit()
            
    elif action == "leave":
        if player:
            # Reembolsar balance a la wallet
            user = await db.get(User, user_id)
            user.balance += Decimal(str(player["balance_in_play"]))
            tx = Transaction(user_id=user_id, amount=Decimal(str(player["balance_in_play"])), transaction_type="CASH_OUT", description="Poker Cash Out")
            db.add(tx)
            
            players.remove(player)
            table.players_data = players
            if len(players) == 0:
                table.status = "WAITING_PLAYERS"
                table.community_cards = []
                table.pot = 0
            flag_modified(table, "players_data")
            db.add(table)
            await db.commit()
            
    elif action == "start_game":
        if table.status in ["WAITING_PLAYERS", "SHOWDOWN"] and len(players) >= 2:
            # Mover boton
            if table.status == "SHOWDOWN":
                table.dealer_button_index = (table.dealer_button_index + 1) % len(players)
                
            table.status = "PRE_FLOP"
            table.community_cards = []
            table.pot = 0
            deck = get_deck()
            random.shuffle(deck)
            table.deck = deck
            
            # Reset player states
            for p in players:
                p["status"] = "ACTIVE"
                p["hand"] = [deck.pop(), deck.pop()]
                p["round_bet"] = 0
                p["acted_this_round"] = False
                p["best_hand_name"] = ""
                
            sb_idx = (table.dealer_button_index + 1) % len(players)
            bb_idx = (table.dealer_button_index + 2) % len(players)
            
            # Post blinds
            sb_amount = min(Decimal(str(players[sb_idx]["balance_in_play"])), table.small_blind)
            bb_amount = min(Decimal(str(players[bb_idx]["balance_in_play"])), table.big_blind)
            
            players[sb_idx]["balance_in_play"] -= float(sb_amount)
            players[sb_idx]["round_bet"] = float(sb_amount)
            
            players[bb_idx]["balance_in_play"] -= float(bb_amount)
            players[bb_idx]["round_bet"] = float(bb_amount)
            
            table.current_bet = float(bb_amount)
            
            table.current_turn_index = (table.dealer_button_index + 3) % len(players)
            
            table.players_data = players
            flag_modified(table, "players_data")
            flag_modified(table, "deck")
            flag_modified(table, "community_cards")
            db.add(table)
            await db.commit()
            
    elif action in ["fold", "check", "call", "raise"]:
        if table.status not in ["WAITING_PLAYERS", "SHOWDOWN"] and player and players.index(player) == table.current_turn_index:
            amount = Decimal(str(action_data.get("amount", 0)))
            
            if action == "fold":
                player["status"] = "FOLDED"
            
            elif action == "check":
                if float(player["round_bet"]) < float(table.current_bet):
                    return await get_poker_state(db, table_id) # Invalid check
                    
            elif action == "call":
                call_amount = Decimal(str(table.current_bet)) - Decimal(str(player["round_bet"]))
                call_amount = min(call_amount, Decimal(str(player["balance_in_play"])))
                player["balance_in_play"] -= float(call_amount)
                player["round_bet"] += float(call_amount)
                if player["balance_in_play"] <= 0:
                    player["status"] = "ALL_IN"
                    
            elif action == "raise":
                total_bet = Decimal(str(table.current_bet)) + amount
                raise_amount = total_bet - Decimal(str(player["round_bet"]))
                raise_amount = min(raise_amount, Decimal(str(player["balance_in_play"])))
                
                player["balance_in_play"] -= float(raise_amount)
                player["round_bet"] += float(raise_amount)
                table.current_bet = float(player["round_bet"])
                
                if player["balance_in_play"] <= 0:
                    player["status"] = "ALL_IN"
                    
                # Other players need to act again
                for p in players:
                    if p != player and p["status"] == "ACTIVE":
                        p["acted_this_round"] = False
                        
            player["acted_this_round"] = True
            
            if check_round_end(table, players):
                await next_street(db, table, players)
            else:
                advance_turn(table, players)
                
            table.players_data = players
            flag_modified(table, "players_data")
            flag_modified(table, "deck")
            flag_modified(table, "community_cards")
            db.add(table)
            await db.commit()

    return await get_poker_state(db, table_id)
