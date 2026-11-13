"""La mesa de generala contra la casa.

Mismo esquema que el truco: la partida no se guarda como estado sino como la
lista de acciones jugadas, y se reconstruye reproduciéndolas sobre el motor
puro. Acá eso además es lo que hace verificables los dados, porque el flujo se
consume en orden: repetir las mismas acciones sobre el mismo seed devuelve
exactamente las mismas tiradas.

La plata: el jugador apuesta al empezar y cobra `MULTIPLICADOR_DE_PAGO` si gana.
El empate devuelve la apuesta, que en la generala no es un caso raro de manual
—pasa cerca de una vez cada cien partidas— y había que decidirlo: quedársela
sería cobrarle a los dos por no perder.
"""

from decimal import ROUND_DOWN, Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.games.generala import bot
from app.modules.games.generala.partida import Partida, reconstruir_desde
from app.modules.games.generala.turno import aplicar_accion
from app.modules.games.infrastructure.models import Bet, GeneralaPartida
from app.modules.games.shared.betting import parse_bet_amount
from app.modules.games.shared.semillas import (
    generar_client_seed,
    generar_server_seed,
    hashear_seed,
)
from app.modules.wallet.application.balance import credit, debit
from app.modules.wallet.infrastructure.models import Transaction

GAME_ID = "generala"
JUGADOR = 0
CASA = 1

# Medido con `simular.py rivales`, 1500 partidas por rival, bot a full:
#
#   rival                        gana el jugador   pago de equilibrio
#   calculadora (1 tirada vista)      47.7%              2.078
#   heuristica (humano razonable)     35.0%              2.848
#
# Con 1.95 le vuelve el 93.9% de lo apostado al que juega al maximo y el 68.6%
# al que juega como en una mesa. Queda abajo del equilibrio del techo a
# proposito: ese techo mira una sola tirada adelante, y un jugador con una
# tabla de programacion dinamica juega mejor que eso.
#
# Lo que hay que saber antes de tocar este numero: el spread entre esos dos
# RTP no se arregla con el multiplicador. Con pago binario por ganar o perder,
# la diferencia de retorno entre un casual y un experto es exactamente la
# diferencia de habilidad, y mover el multiplicador los desplaza a los dos
# juntos. Bajarle el nivel al bot (`bot.PROBABILIDAD_DE_CALCULAR`) tampoco:
# medido en 0.0, el casual pasa a 49.4% de victorias y el experto a 66.6%, o
# sea el mismo spread corrido. Para que el casual no deje el 31% hay que
# cambiar la forma del pago —pagar por puntaje y no por ganar— y eso es una
# decision de producto, no un ajuste.
MULTIPLICADOR_DE_PAGO = Decimal("1.95")

APUESTA_MAXIMA = Decimal("500.00")
CENTAVOS = Decimal("0.01")


async def partida_abierta(db: AsyncSession, user_id: int):
    return await db.scalar(
        select(GeneralaPartida)
        .where(
            GeneralaPartida.user_id == user_id,
            GeneralaPartida.terminada.is_(False),
        )
        .limit(1)
    )


def reconstruir(fila: GeneralaPartida) -> Partida:
    """Rehace la partida reproduciendo las acciones guardadas."""
    return reconstruir_desde(
        fila.server_seed,
        fila.client_seed,
        fila.nonce,
        fila.empieza,
        fila.acciones,
    )


def _avanzar(partida: Partida, acciones: list) -> None:
    """Juega la casa hasta que le toque al jugador o termine la partida."""
    while not partida.terminada and partida.en_turno == CASA:
        accion = bot.decidir(partida, CASA)
        if accion is None:
            break

        aplicar_accion(partida.turno, accion)
        acciones.append({"jugador": CASA, "accion": accion})

        if partida.turno.terminado:
            partida.cerrar_turno()


async def _proximo_empieza(db: AsyncSession, user_id: int) -> int:
    """Se alterna quién arranca entre partidas del mismo jugador.

    Empezar vale poco —medido, 0,3 puntos de porcentaje— pero vale algo, y
    dárselo siempre al mismo sería regalarlo.
    """
    jugadas = await db.scalar(
        select(func.count())
        .select_from(GeneralaPartida)
        .where(GeneralaPartida.user_id == user_id)
    )
    return (jugadas or 0) % 2


async def empezar_partida(db: AsyncSession, user_id: int, monto_crudo) -> dict:
    if await partida_abierta(db, user_id) is not None:
        raise HTTPException(status_code=400, detail="Ya tenés una partida sin terminar")

    apuesta = parse_bet_amount(monto_crudo, max_bet=APUESTA_MAXIMA)
    if apuesta is None:
        raise HTTPException(status_code=400, detail="Monto de apuesta inválido")

    empieza = await _proximo_empieza(db, user_id)

    if not await debit(db, user_id, apuesta):
        raise HTTPException(status_code=400, detail="Saldo insuficiente")

    db.add(
        Transaction(
            user_id=user_id,
            amount=apuesta,
            transaction_type="BET",
            description="Generala",
        )
    )

    server_seed = generar_server_seed()
    fila = GeneralaPartida(
        user_id=user_id,
        apuesta=apuesta,
        server_seed=server_seed,
        server_seed_hash=hashear_seed(server_seed),
        client_seed=generar_client_seed(),
        nonce=0,
        empieza=empieza,
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

    # Si arranca la casa, juega antes de devolver el estado.
    partida = reconstruir(fila)
    acciones = list(fila.acciones)
    _avanzar(partida, acciones)
    fila.acciones = acciones

    if partida.terminada:
        # Generala servida de la casa en la primera: pasa, y hay que liquidar.
        await _liquidar(db, fila, partida)

    await db.commit()
    await db.refresh(fila)

    return _respuesta(fila, partida)


async def jugar_accion(db: AsyncSession, user_id: int, accion: str) -> dict:
    fila = await partida_abierta(db, user_id)
    if fila is None:
        raise HTTPException(status_code=404, detail="No tenés una partida abierta")

    partida = reconstruir(fila)

    if partida.terminada:
        raise HTTPException(status_code=400, detail="La partida ya terminó")

    if partida.en_turno != JUGADOR:
        raise HTTPException(status_code=400, detail="No es tu turno")

    acciones = list(fila.acciones)

    try:
        aplicar_accion(partida.turno, accion)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    acciones.append({"jugador": JUGADOR, "accion": accion})

    if partida.turno.terminado:
        partida.cerrar_turno()

    _avanzar(partida, acciones)

    fila.acciones = acciones

    if partida.terminada:
        await _liquidar(db, fila, partida)

    await db.commit()
    await db.refresh(fila)

    return _respuesta(fila, partida)


async def _liquidar(db: AsyncSession, fila: GeneralaPartida, partida: Partida) -> None:
    fila.terminada = True
    fila.ganador = partida.ganador

    if partida.ganador is None:
        # Empate: vuelve la apuesta, ni ganó ni perdió.
        pago = Decimal(fila.apuesta)
    elif partida.ganador == JUGADOR:
        pago = (Decimal(fila.apuesta) * MULTIPLICADOR_DE_PAGO).quantize(
            CENTAVOS, rounding=ROUND_DOWN
        )
    else:
        pago = Decimal("0.00")

    fila.payout = pago

    if pago > 0 and await credit(db, fila.user_id, pago):
        db.add(
            Transaction(
                user_id=fila.user_id,
                amount=pago,
                transaction_type="PAYOUT",
                description="Generala",
            )
        )

    db.add(
        Bet(
            user_id=fila.user_id,
            game_id=GAME_ID,
            bet_amount=fila.apuesta,
            payout=fila.payout,
            result_data={
                "totales": [partida.total(0), partida.total(1)],
                "ganador": partida.ganador,
                "generala_servida_de": partida.generala_servida_de,
                "server_seed": fila.server_seed,
                "server_seed_hash": fila.server_seed_hash,
                "client_seed": fila.client_seed,
                "acciones": fila.acciones,
            },
        )
    )


def _respuesta(fila: GeneralaPartida, partida: Partida) -> dict:
    estado = partida.estado(para=JUGADOR)
    estado["partida_id"] = fila.id
    estado["apuesta"] = str(fila.apuesta)
    estado["payout"] = str(fila.payout)
    estado["multiplicador"] = str(MULTIPLICADOR_DE_PAGO)
    estado["server_seed_hash"] = fila.server_seed_hash
    estado["client_seed"] = fila.client_seed
    estado["nonce"] = fila.nonce

    # El seed se revela recién cuando la partida terminó: con el seed en la
    # mano el jugador sabría qué dados vienen.
    estado["server_seed"] = fila.server_seed if fila.terminada else None
    estado["acciones_jugadas"] = len(fila.acciones)

    return estado
