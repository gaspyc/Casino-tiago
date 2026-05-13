import random
from decimal import Decimal
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.games.infrastructure.models import BlackjackTable
from app.modules.games.application.blackjack_service import calculate_score, get_deck
from sqlalchemy.orm.attributes import flag_modified
from app.modules.users.infrastructure.models import User
from app.modules.wallet.infrastructure.models import Transaction

def default_player(user_id: int, username: str) -> dict:
    return {
        "user_id": user_id,
        "username": username,
        "bet": 0,
        "hand": [],
        "status": "WAITING" # WAITING, BETTING, PLAYING, STOOD, BUSTED
    }

async def get_table_state(db: AsyncSession, table_id: int) -> dict:
    table = await db.get(BlackjackTable, table_id)
    if not table:
        return None
        
    # El dealer oculta su segunda carta hasta que status sea RESOLVED
    dealer_hand = []
    if table.dealer_hand and len(table.dealer_hand) > 0:
        if table.status in ["DEALING", "PLAYING"]:
            dealer_hand = [table.dealer_hand[0], "HIDDEN"]
        else:
            dealer_hand = table.dealer_hand
            
    return {
        "id": table.id,
        "name": table.name,
        "status": table.status,
        "dealer_hand": dealer_hand,
        "players": table.players_data,
        "current_turn_index": table.current_turn_index
    }

async def process_ws_action(db: AsyncSession, table_id: int, user_id: int, action_data: dict) -> dict:
    table = await db.get(BlackjackTable, table_id)
    if not table:
        return None
        
    action = action_data.get("action")
    players: List[dict] = list(table.players_data) if table.players_data else []
    
    player = next((p for p in players if p["user_id"] == user_id), None)
    
    if action == "join":
        if not player:
            user = await db.get(User, user_id)
            players.append(default_player(user_id, user.username if user.username else f"User {user_id}"))
            table.players_data = players
            flag_modified(table, "players_data")
            flag_modified(table, "deck")
            flag_modified(table, "dealer_hand")
            db.add(table)
            await db.commit()
            
    elif action == "leave":
        if player:
            players.remove(player)
            table.players_data = players
            if len(players) == 0:
                table.status = "WAITING_PLAYERS"
                table.dealer_hand = []
                table.current_turn_index = 0
            db.add(table)
            await db.commit()
            
    elif action == "bet":
        if player and table.status in ["WAITING_PLAYERS", "BETTING", "RESOLVED"]:
            if table.status == "RESOLVED":
                table.status = "BETTING"
                table.dealer_hand = []
                for p in players:
                    p["hand"] = []
                    p["status"] = "WAITING"
            
            bet_amount = Decimal(str(action_data.get("bet_amount", 0)))
            if bet_amount > 0:
                # Cobrar de la billetera
                user = await db.get(User, user_id)
                if user.balance >= bet_amount:
                    user.balance -= bet_amount
                    tx = Transaction(user_id=user_id, amount=bet_amount, transaction_type="BET", description="Multiplayer Blackjack")
                    db.add(tx)
                    
                    player["bet"] = float(bet_amount) # JSON no soporta Decimal nativo, lo guardamos como float en el dict
                    player["status"] = "BETTING"
                    table.players_data = players
                    table.status = "BETTING"
                    flag_modified(table, "players_data")
                    flag_modified(table, "deck")
                    flag_modified(table, "dealer_hand")
                    db.add(table)
                    await db.commit()
                
    elif action == "start_deal":
        # Any user can start the deal if there are players with bets
        betting_players = [p for p in players if p["bet"] > 0]
        if len(betting_players) > 0 and table.status == "BETTING":
            table.status = "PLAYING"
            deck = get_deck()
            random.shuffle(deck)
            
            for p in players:
                if p["bet"] > 0:
                    p["hand"] = [deck.pop(), deck.pop()]
                    p["status"] = "PLAYING"
                
            table.dealer_hand = [deck.pop(), deck.pop()]
            table.deck = deck
            table.current_turn_index = 0
            
            # Skip players who didn't bet
            while table.current_turn_index < len(players) and players[table.current_turn_index]["bet"] == 0:
                table.current_turn_index += 1
                
            table.players_data = players
            flag_modified(table, "players_data")
            flag_modified(table, "deck")
            flag_modified(table, "dealer_hand")
            db.add(table)
            await db.commit()
            
    elif action == "hit":
        if table.status == "PLAYING" and player and players.index(player) == table.current_turn_index:
            deck = list(table.deck)
            player["hand"].append(deck.pop())
            if calculate_score(player["hand"]) > 21:
                player["status"] = "BUSTED"
                table.current_turn_index += 1
                while table.current_turn_index < len(players) and players[table.current_turn_index]["bet"] == 0:
                    table.current_turn_index += 1
                
            table.deck = deck
            table.players_data = players
            flag_modified(table, "players_data")
            flag_modified(table, "deck")
            flag_modified(table, "dealer_hand")
            db.add(table)
            await db.commit()
            
    elif action == "stand":
        if table.status == "PLAYING" and player and players.index(player) == table.current_turn_index:
            player["status"] = "STOOD"
            table.current_turn_index += 1
            while table.current_turn_index < len(players) and players[table.current_turn_index]["bet"] == 0:
                table.current_turn_index += 1
                
            table.players_data = players
            flag_modified(table, "players_data")
            flag_modified(table, "deck")
            flag_modified(table, "dealer_hand")
            db.add(table)
            await db.commit()
            
    # Auto-resolve
    if table.status == "PLAYING" and table.current_turn_index >= len(players):
        deck = list(table.deck)
        dealer_hand = list(table.dealer_hand)
        while calculate_score(dealer_hand) < 17:
            dealer_hand.append(deck.pop())
            
        dealer_score = calculate_score(dealer_hand)
        
        for p in players:
            if p["bet"] > 0 and p["status"] in ["STOOD", "PLAYING"]:
                p_score = calculate_score(p["hand"])
                payout = 0
                
                if p_score <= 21:
                    if dealer_score > 21 or p_score > dealer_score:
                        payout = p["bet"] * 2
                    elif p_score == dealer_score:
                        payout = p["bet"]
                        
                if payout > 0:
                    payout_dec = Decimal(str(payout))
                    user = await db.get(User, p["user_id"])
                    user.balance += payout_dec
                    tx = Transaction(user_id=p["user_id"], amount=payout_dec, transaction_type="PAYOUT", description="Multiplayer Blackjack")
                    db.add(tx)
                
                p["bet"] = 0 # reset bet for next round
                
        table.dealer_hand = dealer_hand
        table.deck = deck
        table.status = "RESOLVED"
        table.players_data = players
        flag_modified(table, "players_data")
        flag_modified(table, "deck")
        flag_modified(table, "dealer_hand")
        db.add(table)
        await db.commit()
        
    return await get_table_state(db, table_id)
