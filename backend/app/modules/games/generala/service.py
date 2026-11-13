"""La mesa de generala contra la casa.

Mismo esquema que el truco: la partida no se guarda como estado sino como la
lista de acciones jugadas, y se reconstruye reproduciéndolas sobre el motor
puro. Acá eso además es lo que hace verificables los dados, porque el flujo se
consume en orden: repetir las mismas acciones sobre el mismo seed devuelve
exactamente las mismas tiradas.

La plata: se cobra por PUNTAJE, no por ganarle a la casa. Cuánto paga cada
puntaje está en `pagos.py`, con la medición que lo justifica. Acá alcanza con
saber por qué: con pago binario la brecha de retorno entre un casual y un
experto era 1,37x sobre una diferencia de puntaje de 1,20x, porque ganar o
perder es un umbral y cerca del umbral unos pocos puntos deciden toda la
apuesta. El casual dejaba el 31%.

La casa sigue jugando y su puntaje se muestra, pero no decide lo que cobrás.
Y como no lo decide, su generala servida ya no corta la partida: cortarla
sería sacarte plata con un volado que no jugaste. La tuya tampoco corta, y se
paga aparte. El duelo clásico —servida gana en el acto, gana el que más
suma— vive en la mesa entre jugadores, en `mesas.py`.
"""

from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.games.generala import bot, pagos
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

# Quién corta la partida con una generala servida. Nadie: pagando por
# puntaje, la servida de la casa no tiene por qué cortarte —no jugaste ese
# volado y te recortaría la planilla— y la tuya se cobra aparte, sin
# necesidad de terminar la partida antes.
CORTA_SERVIDA_DE = ()

# La regla con la que se jugaban las partidas viejas, que pagaban 1,95x por
# ganarle a la casa. Se conserva para que sigan reconstruyendo igual: con otra
# regla las mismas acciones dan otra partida y dejan de verificar. Lo que
# cobraron ya está guardado en cada fila, así que el multiplicador viejo no
# hace falta tenerlo acá.
CORTA_SERVIDA_DE_LAS_VIEJAS = (0, 1)

APUESTA_MAXIMA = pagos.APUESTA_MAXIMA


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
    """Rehace la partida reproduciendo las acciones guardadas.

    La regla de la servida sale de la fila, no de la constante de hoy: una
    partida jugada con la regla vieja tiene que seguir rehaciéndose con la
    regla vieja o deja de verificar.
    """
    corta = (
        CORTA_SERVIDA_DE if fila.paga_por_puntaje else CORTA_SERVIDA_DE_LAS_VIEJAS
    )
    return reconstruir_desde(
        fila.server_seed,
        fila.client_seed,
        fila.nonce,
        fila.empieza,
        fila.acciones,
        corta_servida_de=corta,
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

    puntaje = partida.total(JUGADOR)
    servida = partida.anoto_generala_servida(JUGADOR)

    fila.puntaje = puntaje
    fila.multiplicador = pagos.multiplicador(puntaje, servida)
    # El pago sale de la fracción exacta, no del multiplicador mostrado:
    # truncar y después multiplicar se come RTP en los pagos chicos.
    pago = pagos.premio(Decimal(fila.apuesta), puntaje, servida)

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
                "puntaje": puntaje,
                "generala_servida": servida,
                "multiplicador": str(fila.multiplicador),
                "equilibrio": pagos.PUNTAJE_DE_EQUILIBRIO,
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
    # Lo que cobrarías si la partida cerrara con la planilla como está. Es
    # información honesta y además es la que hace entendible el pago: el
    # jugador ve subir el número a medida que anota.
    puntaje = partida.total(JUGADOR)
    servida = partida.anoto_generala_servida(JUGADOR)

    estado["puntaje"] = puntaje
    estado["generala_servida"] = servida
    estado["multiplicador"] = str(pagos.multiplicador(puntaje, servida))
    estado["equilibrio"] = pagos.PUNTAJE_DE_EQUILIBRIO
    estado["premio_servida"] = str(pagos.PREMIO_SERVIDA)
    estado["paga_por_puntaje"] = bool(fila.paga_por_puntaje)
    estado["proyeccion"] = str(
        pagos.premio(Decimal(fila.apuesta), puntaje, servida)
    )
    estado["server_seed_hash"] = fila.server_seed_hash
    estado["client_seed"] = fila.client_seed
    estado["nonce"] = fila.nonce

    # El seed se revela recién cuando la partida terminó: con el seed en la
    # mano el jugador sabría qué dados vienen.
    estado["server_seed"] = fila.server_seed if fila.terminada else None
    estado["acciones_jugadas"] = len(fila.acciones)

    return estado
