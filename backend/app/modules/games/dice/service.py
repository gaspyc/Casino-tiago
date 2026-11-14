"""La mesa del dice.

Cada jugada sale de la semilla vigente del jugador y de un nonce que se
reserva en la base, igual que plinko y mines. El nonce en la base no es un
detalle: dos jugadas simultáneas con el mismo nonce darían la misma salida y
el jugador no podría distinguir cuál verificó.
"""

from decimal import Decimal
from fractions import Fraction

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.games.dice import reglas
from app.modules.games.dice.fairness import derivar_salida
from app.modules.games.infrastructure.models import Bet, GameSeed
from app.modules.games.shared import compromiso, pagos
from app.modules.games.shared.betting import parse_bet_amount
from app.modules.wallet.application.balance import credit, debit
from app.modules.wallet.infrastructure.models import Transaction

GAME_ID = "dice"

APUESTA_MAXIMA = Decimal("500.00")


async def obtener_semilla_activa(db: AsyncSession, user_id: int) -> GameSeed:
    return await compromiso.obtener_semilla_activa(db, user_id, GAME_ID)


async def rotar_semilla(db: AsyncSession, user_id: int, client_seed: str = None) -> dict:
    """Revela la semilla vigente y deja una nueva.

    Acá no hace falta el candado que tienen el blackjack o la generala: la
    jugada del dice se abre y se cierra en el mismo pedido, así que no existe
    el caso de revelar el seed con algo a medio jugar.
    """
    return await compromiso.rotar_semilla(db, user_id, GAME_ID, client_seed)


describir_semilla = compromiso.describir_semilla


def _objetivo_en_centesimas(crudo) -> int:
    """42.50 -> 4250. Se trabaja en enteros para que no entren flotantes."""
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

    return int(centesimas)


def tabla_de_limites() -> dict:
    """Los extremos que se pueden apostar. La pantalla los usa para los topes."""
    return {
        "salidas": reglas.SALIDAS,
        "rtp": str(pagos.mostrar(reglas.RTP, 4)),
        "chance_minima": str(
            pagos.mostrar(Fraction(reglas.CHANCE_MINIMA * 100, reglas.SALIDAS), 2)
        ),
        "chance_maxima": str(
            pagos.mostrar(Fraction(reglas.CHANCE_MAXIMA * 100, reglas.SALIDAS), 2)
        ),
        "multiplicador_maximo": str(pagos.mostrar(reglas.MULTIPLICADOR_MAXIMO, 2)),
        "multiplicador_minimo": str(
            pagos.mostrar(
                reglas.RTP * reglas.SALIDAS / reglas.CHANCE_MAXIMA, 4
            )
        ),
        "apuesta_maxima": str(APUESTA_MAXIMA),
        "lados": list(reglas.LADOS),
    }


def cotizar(objetivo_crudo, lado: str) -> dict:
    """Qué paga esta apuesta, sin jugarla. Para que la pantalla no adivine."""
    objetivo = _objetivo_en_centesimas(objetivo_crudo)

    if not reglas.objetivo_valido(objetivo, lado):
        raise HTTPException(
            status_code=400,
            detail="Esa apuesta queda fuera de los límites: la chance va de %s%% a %s%%"
            % (
                pagos.mostrar(Fraction(reglas.CHANCE_MINIMA * 100, reglas.SALIDAS), 2),
                pagos.mostrar(Fraction(reglas.CHANCE_MAXIMA * 100, reglas.SALIDAS), 2),
            ),
        )

    chance = reglas.chance_de(objetivo, lado)
    multiplicador = reglas.multiplicador_de(objetivo, lado)

    return {
        "objetivo": reglas.como_texto(objetivo),
        "lado": lado,
        "ganadoras": reglas.ganadoras(objetivo, lado),
        "chance": str(pagos.mostrar(chance * 100, 2)),
        "multiplicador": str(pagos.mostrar(multiplicador, 4)),
    }


async def jugar(db: AsyncSession, user_id: int, monto_crudo, objetivo_crudo, lado: str) -> dict:
    objetivo = _objetivo_en_centesimas(objetivo_crudo)

    if not reglas.objetivo_valido(objetivo, lado):
        raise HTTPException(status_code=400, detail="Esa apuesta queda fuera de los límites")

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
            description="Dice",
        )
    )

    nonce = await compromiso.siguiente_nonce(db, semilla)
    salida = derivar_salida(semilla.server_seed, semilla.client_seed, nonce)

    gano = reglas.paga(salida, objetivo, lado)
    multiplicador = reglas.multiplicador_de(objetivo, lado)

    # El premio sale de la fracción exacta, nunca del multiplicador mostrado.
    premio = pagos.premio(apuesta, multiplicador) if gano else Decimal("0.00")

    if premio > 0 and await credit(db, user_id, premio):
        db.add(
            Transaction(
                user_id=user_id,
                amount=premio,
                transaction_type="PAYOUT",
                description="Dice",
            )
        )

    resultado = {
        "salida": reglas.como_texto(salida),
        "salida_cruda": salida,
        "objetivo": reglas.como_texto(objetivo),
        "lado": lado,
        "gano": gano,
        "apuesta": str(apuesta),
        "payout": str(premio),
        "multiplicador": str(pagos.mostrar(multiplicador, 4)),
        "chance": str(pagos.mostrar(reglas.chance_de(objetivo, lado) * 100, 2)),
        # Lo que hace verificable la jugada: el hash ya estaba publicado.
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
