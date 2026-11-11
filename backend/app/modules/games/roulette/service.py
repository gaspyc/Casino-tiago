from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.games.infrastructure.models import Bet
from app.modules.games.roulette.schemas import BetResultDetail, GameResultResponse, RouletteBetCreate
from app.modules.wallet.infrastructure.models import Transaction
from app.modules.wallet.application.balance import credit, debit
from app.modules.games.roulette.paytable import (
    ROULETTE_NUMBERS,
    calcular_multiplicador,
    color_de,
    paridad_de,
)
from app.modules.games.shared import rng


async def play_roulette_service(
    db: AsyncSession,
    user_id: int,
    bet_data: RouletteBetCreate,
) -> GameResultResponse:
    total_bet_amount = sum(item.bet_amount for item in bet_data.bets)

    if not await debit(db, user_id, total_bet_amount):
        raise HTTPException(status_code=400, detail="Saldo insuficiente para el total de la apuesta")

    winning_number = rng.choice(ROULETTE_NUMBERS)
    winning_color = color_de(winning_number)
    winning_parity = paridad_de(winning_number)

    total_payout = Decimal("0.0")
    bet_details = []

    for item in bet_data.bets:
        payout_multiplier = calcular_multiplicador(
            item.bet_type, item.bet_value, winning_number
        )
        is_win = payout_multiplier > 0

        payout = item.bet_amount * payout_multiplier
        total_payout += payout

        bet_details.append(
            BetResultDetail(
                bet_type=item.bet_type,
                bet_value=item.bet_value,
                bet_amount=item.bet_amount,
                payout=payout,
                win=is_win,
            )
        )

    if total_payout > 0:
        await credit(db, user_id, total_payout)

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
            "bets": [detail.model_dump(mode="json") for detail in bet_details],
        },
    )
    db.add(bet_record)

    tx_bet = Transaction(
        user_id=user_id,
        amount=total_bet_amount,
        transaction_type="BET",
        description="Roulette",
    )
    db.add(tx_bet)

    if total_payout > 0:
        tx_win = Transaction(
            user_id=user_id,
            amount=total_payout,
            transaction_type="PAYOUT",
            description="Roulette",
        )
        db.add(tx_win)

    await db.commit()

    return GameResultResponse(
        game_id="roulette",
        total_bet_amount=total_bet_amount,
        total_payout=total_payout,
        net_profit=total_payout - total_bet_amount,
        result_data=result_data,
        bet_details=bet_details,
    )
