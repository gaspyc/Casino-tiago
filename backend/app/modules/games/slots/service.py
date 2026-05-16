import random
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.games.infrastructure.models import Bet
from app.modules.games.slots.schemas import SlotBetCreate, SlotResultResponse
from app.modules.users.infrastructure.models import User
from app.modules.wallet.infrastructure.models import Transaction

SLOT_SYMBOLS = ["🍒", "🍋", "🍊", "🍇", "🔔", "💎", "7️⃣"]


async def play_slots_service(
    db: AsyncSession,
    user_id: int,
    bet_data: SlotBetCreate,
) -> SlotResultResponse:
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    if user.balance < bet_data.bet_amount:
        raise HTTPException(status_code=400, detail="Saldo insuficiente")

    user.balance -= bet_data.bet_amount

    result_line = [random.choice(SLOT_SYMBOLS) for _ in range(3)]

    payout_multiplier = Decimal("0.0")

    if result_line[0] == result_line[1] == result_line[2]:
        symbol = result_line[0]
        if symbol == "7️⃣":
            payout_multiplier = Decimal("100.0")
        elif symbol == "💎":
            payout_multiplier = Decimal("50.0")
        elif symbol == "🔔":
            payout_multiplier = Decimal("30.0")
        elif symbol == "🍇":
            payout_multiplier = Decimal("20.0")
        elif symbol == "🍊":
            payout_multiplier = Decimal("15.0")
        elif symbol == "🍋":
            payout_multiplier = Decimal("10.0")
        elif symbol == "🍒":
            payout_multiplier = Decimal("5.0")
    else:
        cherries = result_line.count("🍒")
        if cherries >= 2:
            payout_multiplier = Decimal("2.0")

    total_payout = bet_data.bet_amount * payout_multiplier

    if total_payout > 0:
        user.balance += total_payout

    result_data = {"line": result_line}

    bet_record = Bet(
        user_id=user_id,
        game_id="slots",
        bet_amount=bet_data.bet_amount,
        payout=total_payout,
        result_data=result_data,
    )
    db.add(bet_record)

    tx_bet = Transaction(
        user_id=user_id,
        amount=bet_data.bet_amount,
        transaction_type="BET",
        description="Slots",
    )
    db.add(tx_bet)

    if total_payout > 0:
        tx_win = Transaction(
            user_id=user_id,
            amount=total_payout,
            transaction_type="PAYOUT",
            description="Slots",
        )
        db.add(tx_win)

    await db.commit()

    return SlotResultResponse(
        game_id="slots",
        bet_amount=bet_data.bet_amount,
        total_payout=total_payout,
        net_profit=total_payout - bet_data.bet_amount,
        result_data=result_data,
    )
