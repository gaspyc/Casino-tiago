from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.games.infrastructure.models import Bet
from app.modules.games.slots.schemas import SlotBetCreate, SlotResultResponse
from app.modules.wallet.infrastructure.models import Transaction
from app.modules.wallet.application.balance import credit, debit
from app.modules.games.slots.paytable import calcular_multiplicador, girar


async def play_slots_service(
    db: AsyncSession,
    user_id: int,
    bet_data: SlotBetCreate,
) -> SlotResultResponse:
    if not await debit(db, user_id, bet_data.bet_amount):
        raise HTTPException(status_code=400, detail="Saldo insuficiente")

    result_line = girar()
    payout_multiplier = calcular_multiplicador(result_line)

    total_payout = bet_data.bet_amount * payout_multiplier

    if total_payout > 0:
        await credit(db, user_id, total_payout)

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
