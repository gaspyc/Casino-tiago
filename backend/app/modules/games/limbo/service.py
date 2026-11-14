"""La mesa del limbo.

Misma estructura que el dice: semilla del jugador, nonce reservado en la base,
jugada que abre y cierra en el mismo pedido.
"""

from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.games.infrastructure.models import Bet, GameSeed
from app.modules.games.limbo import reglas
from app.modules.games.shared import compromiso, pagos
from app.modules.games.shared.betting import parse_bet_amount
from app.modules.wallet.application.balance import credit, debit
from app.modules.wallet.infrastructure.models import Transaction

GAME_ID = "limbo"

APUESTA_MAXIMA = Decimal("500.00")


async def obtener_semilla_activa(db: AsyncSession, user_id: int) -> GameSeed:
    return await compromiso.obtener_semilla_activa(db, user_id, GAME_ID)


async def rotar_semilla(db: AsyncSession, user_id: int, client_seed: str = None) -> dict:
    return await compromiso.rotar_semilla(db, user_id, GAME_ID, client_seed)


describir_semilla = compromiso.describir_semilla


def _objetivo_en_centesimas(crudo) -> int:
    """2.50 -> 250. En enteros, para que no entren flotantes."""
    try:
        valor = Decimal(str(crudo))
    except Exception:
        raise HTTPException(status_code=400, detail="Objetivo inválido")

    if not valor.is_finite():
        raise HTTPException(status_code=400, detail="Objetivo inválido")

    centesimas = valor * 100
    if centesimas != centesimas.to_integral_value():
        raise HTTPException(
            status_code=400, detail="El objetivo va con hasta dos decimales"
        )

    objetivo = int(centesimas)

    if not reglas.objetivo_valido(objetivo):
        raise HTTPException(
            status_code=400,
            detail="El objetivo va de %sx a %sx"
            % (
                reglas.como_texto(reglas.OBJETIVO_MINIMO),
                reglas.como_texto(reglas.OBJETIVO_MAXIMO),
            ),
        )

    return objetivo


def tabla_de_limites() -> dict:
    return {
        "objetivo_minimo": reglas.como_texto(reglas.OBJETIVO_MINIMO),
        "objetivo_maximo": reglas.como_texto(reglas.OBJETIVO_MAXIMO),
        "rtp": str(pagos.mostrar(reglas.RTP, 4)),
        "apuesta_maxima": str(APUESTA_MAXIMA),
        # El limbo es el crash de un jugador: misma distribución, misma cuenta
        # para verificar, misma ventaja de la casa.
        "misma_distribucion_que": "crash",
    }


def cotizar(objetivo_crudo) -> dict:
    """La chance de este objetivo, sin jugarlo."""
    objetivo = _objetivo_en_centesimas(objetivo_crudo)
    chance = reglas.chance_de(objetivo)

    return {
        "objetivo": reglas.como_texto(objetivo),
        "chance": str(pagos.mostrar(chance * 100, 4)),
        "multiplicador": reglas.como_texto(objetivo),
    }


async def jugar(db: AsyncSession, user_id: int, monto_crudo, objetivo_crudo) -> dict:
    objetivo = _objetivo_en_centesimas(objetivo_crudo)

    apuesta = parse_bet_amount(monto_crudo, max_bet=APUESTA_MAXIMA)
    if apuesta is None:
        raise HTTPException(status_code=400, detail="Monto de apuesta inválido")

    semilla = await obtener_semilla_activa(db, user_id)

    if not await debit(db, user_id, apuesta):
        raise HTTPException(status_code=400, detail="Saldo insuficiente")

    db.add(
        Transaction(
            user_id=user_id,
            amount=apuesta,
            transaction_type="BET",
            description="Limbo",
        )
    )

    nonce = await compromiso.siguiente_nonce(db, semilla)
    sorteado = reglas.calcular_crash_point(
        semilla.server_seed, semilla.client_seed, nonce
    )

    gano = reglas.paga(sorteado, objetivo)
    premio = (
        pagos.premio(apuesta, reglas.multiplicador_de(objetivo))
        if gano
        else Decimal("0.00")
    )

    if premio > 0 and await credit(db, user_id, premio):
        db.add(
            Transaction(
                user_id=user_id,
                amount=premio,
                transaction_type="PAYOUT",
                description="Limbo",
            )
        )

    resultado = {
        "sorteado": "%.2f" % sorteado,
        "objetivo": reglas.como_texto(objetivo),
        "gano": gano,
        "apuesta": str(apuesta),
        "payout": str(premio),
        "multiplicador": reglas.como_texto(objetivo),
        "chance": str(pagos.mostrar(reglas.chance_de(objetivo) * 100, 4)),
        "server_seed_hash": semilla.server_seed_hash,
        "client_seed": semilla.client_seed,
        "nonce": nonce,
    }

    db.add(
        Bet(
            user_id=user_id,
            game_id=GAME_ID,
            bet_amount=apuesta,
            payout=premio,
            result_data=resultado,
        )
    )

    await db.commit()

    return resultado
