"""La mesa de truco contra la casa.

La partida no se guarda como estado sino como la lista de acciones que se
jugaron. Para atender un request se reconstruye reproduciéndolas sobre el motor
puro, que es determinístico: el reparto sale del seed y las decisiones del bot
quedaron anotadas. Así no hay dos versiones del mismo estado que puedan
discrepar, y la partida entera es auditable.

La plata: el jugador apuesta al empezar y cobra `MULTIPLICADOR_DE_PAGO` si gana
la partida. Contra la casa, la ventaja no sale de una tabla de pagos sino de
que el bot juegue mejor que el jugador, así que ese multiplicador y los límites
de apuesta son conservadores a propósito hasta tener medido cómo le va al bot
contra gente de verdad.
"""

from decimal import ROUND_DOWN, Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.games.infrastructure.models import Bet, TrucoPartida
from app.modules.games.shared.betting import parse_bet_amount
from app.modules.games.shared.semillas import (
    generar_client_seed,
    generar_server_seed,
    hashear_seed,
)
from app.modules.games.truco import bot
from app.modules.games.truco.mano import aplicar_accion, jugador_en_turno
from app.modules.games.truco.partida import Partida
from app.modules.games.truco.reglas import PUNTOS_PARTIDA
from app.modules.wallet.application.balance import credit, debit
from app.modules.wallet.infrastructure.models import Transaction

GAME_ID = "truco"
JUGADOR = 0
CASA = 1

# Paga menos del doble porque la partida es pareja: la ventaja de la casa sale
# de la diferencia de juego, no de la tabla. Con 1.90 la casa empata si el
# jugador gana el 52.6% de las partidas.
MULTIPLICADOR_DE_PAGO = Decimal("1.90")

APUESTA_MAXIMA = Decimal("500.00")
CENTAVOS = Decimal("0.01")


async def partida_abierta(db: AsyncSession, user_id: int):
    return await db.scalar(
        select(TrucoPartida)
        .where(TrucoPartida.user_id == user_id, TrucoPartida.terminada.is_(False))
        .limit(1)
    )


def reconstruir(fila: TrucoPartida) -> Partida:
    """Rehace la partida reproduciendo las acciones guardadas."""
    partida = Partida(
        fila.server_seed,
        fila.client_seed,
        fila.nonce_base,
        mano_inicial=JUGADOR,
        objetivo=PUNTOS_PARTIDA,
        con_flor=bool(fila.con_flor),
    )
    partida.nueva_mano()

    for entrada in fila.acciones:
        aplicar_accion(partida.mano_actual, entrada["jugador"], entrada["accion"])

        if partida.mano_actual.terminada:
            partida.cerrar_mano()
            if not partida.terminada:
                partida.nueva_mano()

    return partida


def _avanzar(partida: Partida, acciones: list) -> None:
    """Juega la casa hasta que le toque al jugador o termine la partida."""
    while not partida.terminada:
        mano = partida.mano_actual

        if mano.terminada:
            partida.cerrar_mano()
            if partida.terminada:
                break
            mano = partida.nueva_mano()

        if jugador_en_turno(mano) != CASA:
            break

        accion = bot.decidir(mano, CASA)
        if accion is None:
            break

        aplicar_accion(mano, CASA, accion)
        acciones.append({"jugador": CASA, "accion": accion})


async def empezar_partida(
    db: AsyncSession, user_id: int, monto_crudo, con_flor: bool = False
) -> dict:
    if await partida_abierta(db, user_id) is not None:
        raise HTTPException(status_code=400, detail="Ya tenés una partida sin terminar")

    apuesta = parse_bet_amount(monto_crudo, max_bet=APUESTA_MAXIMA)
    if apuesta is None:
        raise HTTPException(status_code=400, detail="Monto de apuesta inválido")

    if not await debit(db, user_id, apuesta):
        raise HTTPException(status_code=400, detail="Saldo insuficiente")

    db.add(
        Transaction(
            user_id=user_id,
            amount=apuesta,
            transaction_type="BET",
            description="Truco",
        )
    )

    server_seed = generar_server_seed()
    fila = TrucoPartida(
        user_id=user_id,
        apuesta=apuesta,
        server_seed=server_seed,
        server_seed_hash=hashear_seed(server_seed),
        client_seed=generar_client_seed(),
        nonce_base=0,
        con_flor=con_flor,
        acciones=[],
    )
    db.add(fila)

    try:
        await db.commit()
    except IntegrityError:
        # Dos "empezar" simultáneos: el índice único deja una sola abierta.
        await db.rollback()
        await credit(db, user_id, apuesta)
        await db.commit()
        raise HTTPException(status_code=400, detail="Ya tenés una partida sin terminar")

    await db.refresh(fila)

    # Si la casa es mano en la primera, juega antes de devolver el estado.
    partida = reconstruir(fila)
    acciones = list(fila.acciones)
    _avanzar(partida, acciones)
    fila.acciones = acciones
    await db.commit()

    return _respuesta(fila, partida)


async def jugar_accion(db: AsyncSession, user_id: int, accion: str) -> dict:
    fila = await partida_abierta(db, user_id)
    if fila is None:
        raise HTTPException(status_code=404, detail="No tenés una partida abierta")

    partida = reconstruir(fila)
    mano = partida.mano_actual

    if jugador_en_turno(mano) != JUGADOR:
        raise HTTPException(status_code=400, detail="No es tu turno")

    if accion not in mano.acciones(JUGADOR):
        raise HTTPException(status_code=400, detail="Esa acción no se puede ahora")

    acciones = list(fila.acciones)
    aplicar_accion(mano, JUGADOR, accion)
    acciones.append({"jugador": JUGADOR, "accion": accion})

    _avanzar(partida, acciones)

    fila.acciones = acciones

    if partida.terminada:
        await _liquidar(db, fila, partida)

    await db.commit()
    await db.refresh(fila)

    return _respuesta(fila, partida)


async def _liquidar(db: AsyncSession, fila: TrucoPartida, partida: Partida) -> None:
    fila.terminada = True
    fila.ganador = partida.ganador

    if partida.ganador != JUGADOR:
        fila.payout = Decimal("0.00")
    else:
        pago = (Decimal(fila.apuesta) * MULTIPLICADOR_DE_PAGO).quantize(
            CENTAVOS, rounding=ROUND_DOWN
        )
        fila.payout = pago

        if await credit(db, fila.user_id, pago):
            db.add(
                Transaction(
                    user_id=fila.user_id,
                    amount=pago,
                    transaction_type="PAYOUT",
                    description="Truco",
                )
            )

    db.add(
        Bet(
            user_id=fila.user_id,
            game_id=GAME_ID,
            bet_amount=fila.apuesta,
            payout=fila.payout,
            result_data={
                "puntos": list(partida.puntos),
                "manos": partida.manos_jugadas,
                "ganador": partida.ganador,
                "server_seed": fila.server_seed,
                "server_seed_hash": fila.server_seed_hash,
                "client_seed": fila.client_seed,
                "acciones": fila.acciones,
            },
        )
    )


def _respuesta(fila: TrucoPartida, partida: Partida) -> dict:
    estado = partida.estado(para=JUGADOR)
    estado["partida_id"] = fila.id
    estado["apuesta"] = str(fila.apuesta)
    estado["payout"] = str(fila.payout)
    estado["multiplicador"] = str(MULTIPLICADOR_DE_PAGO)
    estado["con_flor"] = bool(fila.con_flor)
    estado["server_seed_hash"] = fila.server_seed_hash
    estado["client_seed"] = fila.client_seed

    # El seed se revela recién cuando la partida terminó.
    estado["server_seed"] = fila.server_seed if fila.terminada else None
    estado["acciones_jugadas"] = len(fila.acciones)

    return estado
