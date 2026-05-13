import random
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from app.modules.games.domain.entities import RouletteBetCreate, GameResultResponse, BetResultDetail, SlotBetCreate, SlotResultResponse
from app.modules.games.infrastructure.models import Bet
from app.modules.users.infrastructure.models import User
from app.modules.wallet.infrastructure.models import Transaction

ROULETTE_NUMBERS = list(range(37))
RED_NUMBERS = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}

async def play_roulette_service(db: AsyncSession, user_id: int, bet_data: RouletteBetCreate) -> GameResultResponse:
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    total_bet_amount = sum(item.bet_amount for item in bet_data.bets)
    
    if user.balance < total_bet_amount:
        raise HTTPException(status_code=400, detail="Saldo insuficiente para el total de la apuesta")
    
    user.balance -= total_bet_amount

    winning_number = random.choice(ROULETTE_NUMBERS)
    winning_color = "green" if winning_number == 0 else ("red" if winning_number in RED_NUMBERS else "black")
    winning_parity = "none" if winning_number == 0 else ("even" if winning_number % 2 == 0 else "odd")

    total_payout = Decimal("0.0")
    bet_details = []

    for item in bet_data.bets:
        is_win = False
        payout_multiplier = Decimal("0.0")

        if item.bet_type == "number":
            if str(winning_number) == item.bet_value:
                is_win = True
                payout_multiplier = Decimal("36.0")
        elif item.bet_type == "color":
            if winning_color == item.bet_value.lower():
                is_win = True
                payout_multiplier = Decimal("2.0")
        elif item.bet_type == "parity":
            if winning_parity == item.bet_value.lower():
                is_win = True
                payout_multiplier = Decimal("2.0")
        elif item.bet_type == "split":
            numbers = item.bet_value.split(",")
            if str(winning_number) in numbers:
                is_win = True
                payout_multiplier = Decimal("18.0")
        elif item.bet_type == "corner":
            numbers = item.bet_value.split(",")
            if str(winning_number) in numbers:
                is_win = True
                payout_multiplier = Decimal("9.0")
        
        payout = item.bet_amount * payout_multiplier if is_win else Decimal("0.0")
        total_payout += payout
        
        bet_details.append(BetResultDetail(
            bet_type=item.bet_type,
            bet_value=item.bet_value,
            bet_amount=item.bet_amount,
            payout=payout,
            win=is_win
        ))

    if total_payout > 0:
        user.balance += total_payout

    result_data = {
        "winning_number": winning_number,
        "winning_color": winning_color,
        "winning_parity": winning_parity,
    }

    bet_record = Bet(
        user_id=user_id,
        game_id="roulette",
        bet_amount=total_bet_amount,
        payout=total_payout,
        result_data={
            "spin_result": result_data,
            "bets": [detail.model_dump(mode='json') for detail in bet_details]
        }
    )
    db.add(bet_record)

    tx_bet = Transaction(user_id=user_id, amount=total_bet_amount, transaction_type="BET", description="Roulette")
    db.add(tx_bet)
    
    if total_payout > 0:
        tx_win = Transaction(user_id=user_id, amount=total_payout, transaction_type="PAYOUT", description="Roulette")
        db.add(tx_win)

    await db.commit()

    return GameResultResponse(
        game_id="roulette",
        total_bet_amount=total_bet_amount,
        total_payout=total_payout,
        net_profit=total_payout - total_bet_amount,
        result_data=result_data,
        bet_details=bet_details
    )

SLOT_SYMBOLS = ["🍒", "🍋", "🍊", "🍇", "🔔", "💎", "7️⃣"]

async def play_slots_service(db: AsyncSession, user_id: int, bet_data: SlotBetCreate) -> SlotResultResponse:
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
    if user.balance < bet_data.bet_amount:
        raise HTTPException(status_code=400, detail="Saldo insuficiente")
        
    user.balance -= bet_data.bet_amount
    
    # Generar 3 símbolos aleatorios
    # Las probabilidades de los símbolos podrían ajustarse, por ahora es equiprobable
    result_line = [random.choice(SLOT_SYMBOLS) for _ in range(3)]
    
    payout_multiplier = Decimal("0.0")
    
    # Calcular pago
    if result_line[0] == result_line[1] == result_line[2]:
        symbol = result_line[0]
        if symbol == "7️⃣": payout_multiplier = Decimal("100.0")
        elif symbol == "💎": payout_multiplier = Decimal("50.0")
        elif symbol == "🔔": payout_multiplier = Decimal("30.0")
        elif symbol == "🍇": payout_multiplier = Decimal("20.0")
        elif symbol == "🍊": payout_multiplier = Decimal("15.0")
        elif symbol == "🍋": payout_multiplier = Decimal("10.0")
        elif symbol == "🍒": payout_multiplier = Decimal("5.0")
    else:
        # Paga doble si hay exactamente 2 cerezas (o al menos 2 cerezas)
        cherries = result_line.count("🍒")
        if cherries >= 2:
            payout_multiplier = Decimal("2.0")
            
    total_payout = bet_data.bet_amount * payout_multiplier
    
    if total_payout > 0:
        user.balance += total_payout
        
    result_data = {
        "line": result_line
    }
    
    bet_record = Bet(
        user_id=user_id,
        game_id="slots",
        bet_amount=bet_data.bet_amount,
        payout=total_payout,
        result_data=result_data
    )
    db.add(bet_record)
    
    tx_bet = Transaction(user_id=user_id, amount=bet_data.bet_amount, transaction_type="BET", description="Slots")
    db.add(tx_bet)
    
    if total_payout > 0:
        tx_win = Transaction(user_id=user_id, amount=total_payout, transaction_type="PAYOUT", description="Slots")
        db.add(tx_win)
        
    await db.commit()
    
    return SlotResultResponse(
        game_id="slots",
        bet_amount=bet_data.bet_amount,
        total_payout=total_payout,
        net_profit=total_payout - bet_data.bet_amount,
        result_data=result_data
    )
