import random
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from app.modules.games.domain.entities import BlackjackBetCreate, BlackjackAction, BlackjackResponse
from app.modules.games.infrastructure.models import BlackjackGame
from app.modules.users.infrastructure.models import User
from app.modules.wallet.infrastructure.models import Transaction

SUITS = ["♠", "♥", "♦", "♣"]
RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]

def get_deck():
    return [f"{rank}{suit}" for suit in SUITS for rank in RANKS]

def calculate_score(hand):
    score = 0
    aces = 0
    for card in hand:
        rank = card[:-1]
        if rank in ["J", "Q", "K"]:
            score += 10
        elif rank == "A":
            aces += 1
            score += 11
        else:
            score += int(rank)
            
    while score > 21 and aces > 0:
        score -= 10
        aces -= 1
        
    return score

def generate_response(game: BlackjackGame, total_payout: Decimal = Decimal("0.0")) -> BlackjackResponse:
    if game.is_split:
        p_scores = [calculate_score(h) for h in game.player_hand]
    else:
        p_scores = calculate_score(game.player_hand)

    d_score = calculate_score([game.dealer_hand[0]]) if game.status == "ACTIVE" else calculate_score(game.dealer_hand)
    d_hand = [game.dealer_hand[0], "HIDDEN"] if game.status == "ACTIVE" else game.dealer_hand

    net_profit = total_payout - game.bet_amount
    if game.is_split:
        net_profit = total_payout - (game.bet_amount * 2) # Apuesta doble

    return BlackjackResponse(
        game_id=game.id,
        bet_amount=game.bet_amount,
        status=game.status,
        player_hand=game.player_hand,
        dealer_hand=d_hand,
        player_score=p_scores,
        dealer_score=d_score,
        net_profit=net_profit,
        total_payout=total_payout,
        is_split=game.is_split,
        active_hand_index=game.active_hand_index
    )

async def start_blackjack_service(db: AsyncSession, user_id: int, bet_data: BlackjackBetCreate) -> BlackjackResponse:
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
    if user.balance < bet_data.bet_amount:
        raise HTTPException(status_code=400, detail="Saldo insuficiente")
        
    user.balance -= bet_data.bet_amount
    
    tx_bet = Transaction(user_id=user_id, amount=bet_data.bet_amount, transaction_type="BET", description="Blackjack")
    db.add(tx_bet)
    
    deck = get_deck()
    random.shuffle(deck)
    
    player_hand = [deck.pop(), deck.pop()]
    dealer_hand = [deck.pop(), deck.pop()]
    
    player_score = calculate_score(player_hand)
    dealer_score = calculate_score(dealer_hand)
    
    status = "ACTIVE"
    total_payout = Decimal("0.0")
    
    if player_score == 21:
        if dealer_score == 21:
            status = "PUSH"
            total_payout = bet_data.bet_amount
        else:
            status = "PLAYER_WON"
            total_payout = bet_data.bet_amount * Decimal("2.5")
            
    if status != "ACTIVE" and total_payout > 0:
        user.balance += total_payout
        tx_win = Transaction(user_id=user_id, amount=total_payout, transaction_type="PAYOUT", description="Blackjack")
        db.add(tx_win)
            
    game = BlackjackGame(
        user_id=user_id,
        bet_amount=bet_data.bet_amount,
        deck=deck,
        player_hand=player_hand,
        dealer_hand=dealer_hand,
        status=status,
        is_split=False,
        active_hand_index=0
    )
    db.add(game)
    await db.commit()
    await db.refresh(game)
    
    return generate_response(game, total_payout)

async def double_blackjack_service(db: AsyncSession, user_id: int, action: BlackjackAction) -> BlackjackResponse:
    game = await db.get(BlackjackGame, action.game_id)
    if not game or game.user_id != user_id:
        raise HTTPException(status_code=404, detail="Juego no encontrado")
        
    if game.status != "ACTIVE":
        raise HTTPException(status_code=400, detail="El juego ya finalizó")
        
    if game.is_split or len(game.player_hand) > 2:
        raise HTTPException(status_code=400, detail="No puedes doblar esta mano")
        
    user = await db.get(User, user_id)
    if user.balance < game.bet_amount:
        raise HTTPException(status_code=400, detail="Saldo insuficiente para doblar")
        
    user.balance -= game.bet_amount
    game.bet_amount += game.bet_amount
    
    tx_bet = Transaction(user_id=user_id, amount=game.bet_amount / 2, transaction_type="BET", description="Blackjack Double")
    db.add(tx_bet)
    
    deck = list(game.deck)
    player_hand = list(game.player_hand)
    player_hand.append(deck.pop())
    
    game.deck = deck
    game.player_hand = player_hand
    
    db.add(game)
    await db.flush()
    
    # Doblar obliga a plantarse justo después de recibir la carta
    if calculate_score(player_hand) > 21:
        game.status = "DEALER_WON"
        await db.commit()
        return generate_response(game, Decimal("0.0"))
        
    return await stand_blackjack_service(db, user_id, action, internal_call=True)

async def split_blackjack_service(db: AsyncSession, user_id: int, action: BlackjackAction) -> BlackjackResponse:
    game = await db.get(BlackjackGame, action.game_id)
    if not game or game.user_id != user_id:
        raise HTTPException(status_code=404, detail="Juego no encontrado")
        
    if game.status != "ACTIVE" or game.is_split or len(game.player_hand) != 2:
        raise HTTPException(status_code=400, detail="No puedes dividir")
        
    rank1 = game.player_hand[0][:-1]
    rank2 = game.player_hand[1][:-1]
    
    if rank1 != rank2 and not (rank1 in ["10","J","Q","K"] and rank2 in ["10","J","Q","K"]):
        raise HTTPException(status_code=400, detail="Las cartas deben tener el mismo valor")
        
    user = await db.get(User, user_id)
    if user.balance < game.bet_amount:
        raise HTTPException(status_code=400, detail="Saldo insuficiente para dividir")
        
    user.balance -= game.bet_amount
    tx_bet = Transaction(user_id=user_id, amount=game.bet_amount, transaction_type="BET", description="Blackjack Split")
    db.add(tx_bet)
    
    deck = list(game.deck)
    hand1 = [game.player_hand[0], deck.pop()]
    hand2 = [game.player_hand[1], deck.pop()]
    
    game.is_split = True
    game.player_hand = [hand1, hand2]
    game.deck = deck
    game.active_hand_index = 0
    
    db.add(game)
    await db.commit()
    
    return generate_response(game)

async def hit_blackjack_service(db: AsyncSession, user_id: int, action: BlackjackAction) -> BlackjackResponse:
    game = await db.get(BlackjackGame, action.game_id)
    if not game or game.user_id != user_id or game.status != "ACTIVE":
        raise HTTPException(status_code=400, detail="Acción inválida")
        
    deck = list(game.deck)
    
    if game.is_split:
        hands = list(game.player_hand)
        active = game.active_hand_index
        # Create a new list for the active hand to avoid mutating the JSONB object directly in a weird way
        current_hand = list(hands[active])
        current_hand.append(deck.pop())
        hands[active] = current_hand
        game.player_hand = hands
        
        score = calculate_score(current_hand)
        if score > 21:
            game.active_hand_index += 1
            if game.active_hand_index > 1:
                return await stand_blackjack_service(db, user_id, action, internal_call=True)
    else:
        player_hand = list(game.player_hand)
        player_hand.append(deck.pop())
        game.player_hand = player_hand
        
        if calculate_score(player_hand) > 21:
            game.status = "DEALER_WON"
            
    game.deck = deck
    db.add(game)
    await db.commit()
    return generate_response(game)

async def stand_blackjack_service(db: AsyncSession, user_id: int, action: BlackjackAction, internal_call: bool = False) -> BlackjackResponse:
    game = await db.get(BlackjackGame, action.game_id)
    if not game or game.user_id != user_id or game.status != "ACTIVE":
        raise HTTPException(status_code=400, detail="Acción inválida")
        
    if game.is_split and not internal_call:
        game.active_hand_index += 1
        if game.active_hand_index <= 1:
            db.add(game)
            await db.commit()
            return generate_response(game)
            
    deck = list(game.deck)
    dealer_hand = list(game.dealer_hand)
    dealer_score = calculate_score(dealer_hand)
    
    while dealer_score < 17:
        dealer_hand.append(deck.pop())
        dealer_score = calculate_score(dealer_hand)
        
    game.deck = deck
    game.dealer_hand = dealer_hand
    
    total_payout = Decimal("0.0")
    user = await db.get(User, user_id)
    
    if game.is_split:
        score1 = calculate_score(game.player_hand[0])
        score2 = calculate_score(game.player_hand[1])
        
        # Eval mano 1
        if score1 <= 21:
            if dealer_score > 21 or score1 > dealer_score:
                total_payout += game.bet_amount * Decimal("2.0")
            elif score1 == dealer_score:
                total_payout += game.bet_amount
                
        # Eval mano 2
        if score2 <= 21:
            if dealer_score > 21 or score2 > dealer_score:
                total_payout += game.bet_amount * Decimal("2.0")
            elif score2 == dealer_score:
                total_payout += game.bet_amount
                
        if total_payout == 0:
            game.status = "DEALER_WON"
        elif total_payout == game.bet_amount * 2:
            game.status = "PUSH" # recuperó lo apostado
        else:
            game.status = "PLAYER_WON" # Ganó al menos una, o recuperó parte
    else:
        player_score = calculate_score(game.player_hand)
        if player_score > 21:
            game.status = "DEALER_WON"
        elif dealer_score > 21 or player_score > dealer_score:
            game.status = "PLAYER_WON"
            total_payout = game.bet_amount * Decimal("2.0")
        elif dealer_score == player_score:
            game.status = "PUSH"
            total_payout = game.bet_amount
        else:
            game.status = "DEALER_WON"
            
    if total_payout > 0:
        user.balance += total_payout
        tx_win = Transaction(user_id=user_id, amount=total_payout, transaction_type="PAYOUT", description="Blackjack")
        db.add(tx_win)
        
    db.add(game)
    await db.commit()
    
    return generate_response(game, total_payout)
