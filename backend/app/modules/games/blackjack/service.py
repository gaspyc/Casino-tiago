from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.games.blackjack.fairness import MAZO, PALOS, VALORES, mezclar_mazo
from app.modules.games.blackjack.schemas import BlackjackAction, BlackjackBetCreate, BlackjackResponse
from app.modules.games.infrastructure.models import BlackjackGame
from app.modules.games.shared import compromiso
from app.modules.wallet.application.balance import credit, debit
from app.modules.wallet.infrastructure.models import Transaction

GAME_ID = "blackjack"

SUITS = PALOS
RANKS = VALORES


def get_deck():
    return list(MAZO)


def _sacar(deck: list) -> str:
    """Saca la carta de arriba.

    Del principio de la lista, no del final: el mazo que el seed fija es el
    orden en que se reparte, así que la primera carta de la lista es la primera
    que sale. Antes se sacaba desde el final, que daba lo mismo con un mazo
    mezclado al azar pero no se puede explicar en una verificación.
    """
    return deck.pop(0)

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
        active_hand_index=game.active_hand_index,
        server_seed_hash=game.server_seed_hash,
        client_seed=game.client_seed,
        nonce=game.nonce,
    )

async def start_blackjack_service(db: AsyncSession, user_id: int, bet_data: BlackjackBetCreate) -> BlackjackResponse:
    semilla = await compromiso.obtener_semilla_activa(db, user_id, GAME_ID)

    if not await debit(db, user_id, bet_data.bet_amount):
        raise HTTPException(status_code=400, detail="Saldo insuficiente")
    
    tx_bet = Transaction(user_id=user_id, amount=bet_data.bet_amount, transaction_type="BET", description="Blackjack")
    db.add(tx_bet)
    
    # El nonce se reserva en la base: dos manos simultáneas no pueden caer en
    # el mismo, que daría el mismo mazo.
    nonce = await compromiso.siguiente_nonce(db, semilla)
    deck = mezclar_mazo(semilla.server_seed, semilla.client_seed, nonce)

    # Como en la mesa: una al jugador, una al crupier, y otra vuelta.
    player_hand = [_sacar(deck)]
    dealer_hand = [_sacar(deck)]
    player_hand.append(_sacar(deck))
    dealer_hand.append(_sacar(deck))
    
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
        await credit(db, user_id, total_payout)
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
        active_hand_index=0,
        seed_id=semilla.id,
        nonce=nonce,
        # Desnormalizado a propósito: el hash queda clavado en la mano aunque
        # después se rote la semilla, así la verificación no depende de un join.
        server_seed_hash=semilla.server_seed_hash,
        client_seed=semilla.client_seed,
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
        
    if not await debit(db, user_id, game.bet_amount):
        raise HTTPException(status_code=400, detail="Saldo insuficiente para doblar")
        
    game.bet_amount += game.bet_amount
    
    tx_bet = Transaction(user_id=user_id, amount=game.bet_amount / 2, transaction_type="BET", description="Blackjack Double")
    db.add(tx_bet)
    
    deck = list(game.deck)
    player_hand = list(game.player_hand)
    player_hand.append(_sacar(deck))
    
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
        
    if not await debit(db, user_id, game.bet_amount):
        raise HTTPException(status_code=400, detail="Saldo insuficiente para dividir")
        
    tx_bet = Transaction(user_id=user_id, amount=game.bet_amount, transaction_type="BET", description="Blackjack Split")
    db.add(tx_bet)
    
    deck = list(game.deck)
    hand1 = [game.player_hand[0], _sacar(deck)]
    hand2 = [game.player_hand[1], _sacar(deck)]
    
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
        current_hand.append(_sacar(deck))
        hands[active] = current_hand
        game.player_hand = hands
        
        score = calculate_score(current_hand)
        if score > 21:
            game.active_hand_index += 1
            if game.active_hand_index > 1:
                return await stand_blackjack_service(db, user_id, action, internal_call=True)
    else:
        player_hand = list(game.player_hand)
        player_hand.append(_sacar(deck))
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
        dealer_hand.append(_sacar(deck))
        dealer_score = calculate_score(dealer_hand)
        
    game.deck = deck
    game.dealer_hand = dealer_hand
    
    total_payout = Decimal("0.0")
    
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
        await credit(db, user_id, total_payout)
        tx_win = Transaction(user_id=user_id, amount=total_payout, transaction_type="PAYOUT", description="Blackjack")
        db.add(tx_win)
        
    db.add(game)
    await db.commit()
    
    return generate_response(game, total_payout)


# ------------------------------ la mano abierta ------------------------------

async def obtener_mano_activa(db: AsyncSession, user_id: int):
    """La mano que el jugador dejó sin terminar, si hay alguna.

    Hacía falta por dos motivos. Uno, la plata: la apuesta se debita al
    repartir y se acredita al resolver, así que una mano abandonada era una
    apuesta perdida sin que el jugador pudiera terminarla, porque la pantalla
    volvía siempre al estado de apostar. Dos, la rotación: el candado de
    `rotar_semilla_blackjack` mira si hay una mano abierta, y una mano que no se
    podía retomar dejaba al jugador sin poder revelar la semilla nunca más.
    """
    game = await db.scalar(
        select(BlackjackGame)
        .where(
            BlackjackGame.user_id == user_id,
            BlackjackGame.status == "ACTIVE",
        )
        .order_by(BlackjackGame.id.desc())
        .limit(1)
    )

    if game is None:
        return None

    return generate_response(game)


# ------------------------------ provably fair ------------------------------

async def obtener_semilla_blackjack(db: AsyncSession, user_id: int):
    """La semilla vigente del jugador en blackjack: sólo su compromiso."""
    return await compromiso.obtener_semilla_activa(db, user_id, GAME_ID)


async def rotar_semilla_blackjack(
    db: AsyncSession,
    user_id: int,
    client_seed: str = None,
) -> dict:
    """Revela la semilla vigente y deja una nueva.

    El candado de la mano abierta es lo que hace que esto sea seguro acá y no
    haga falta en plinko. Una mano de blackjack se resuelve en varias jugadas:
    si el jugador pudiera rotar con la mano en curso, se llevaría el server
    seed, y con el seed rehace el mazo entero. Sabría la carta tapada del
    crupier y qué carta viene si pide una más. Sería un exploit, no una
    verificación.
    """
    abierta = await db.scalar(
        select(BlackjackGame.id)
        .where(
            BlackjackGame.user_id == user_id,
            BlackjackGame.status == "ACTIVE",
        )
        .limit(1)
    )
    if abierta is not None:
        raise HTTPException(
            status_code=409,
            detail="Terminá la mano en curso antes de revelar la semilla",
        )

    return await compromiso.rotar_semilla(db, user_id, GAME_ID, client_seed)
