"""Mesas de truco entre dos jugadores.

Reusa todo lo de la partida contra la casa: el mismo motor, el mismo reparto
verificable y el mismo truco de guardar las acciones en vez del estado. Lo que
cambia es que los dos asientos son personas, así que no hay nadie que adelante
el juego: cada uno juega cuando le toca.

La plata acá no sale de ganarle a la casa sino de una comisión sobre el pozo,
como en las mesas de poker. Es la forma honesta de monetizar un juego de
habilidad: la casa no juega, cobra por poner la mesa.

El plazo de turno
-----------------
Sin plazo, el que va perdiendo nunca está obligado a perder: le alcanza con
dejar de jugar. El rival sólo puede abandonar, y abandonar es entregar la
mesa, así que colgarse sería estrictamente mejor que perder y la apuesta de
los dos quedaría trabada para siempre.

Acá el turno tiene plazo, igual que en las mesas de generala. Si el que tiene
que hablar no habla en `PLAZO_DE_TURNO`, el rival reclama la mesa y se la
lleva. No hace falta ningún proceso de fondo: el plazo se mira cuando alguien
pregunta por la mesa, que es cada un par de segundos mientras hay alguien
mirando.

Sin WebSocket: el cliente pregunta por el estado cada par de segundos. Para un
juego por turnos alcanza, y evita todo el estado de conexión. Si hiciera falta
que sea instantáneo, el canal de Redis que usa crash ya está.
"""

from datetime import datetime, timedelta, timezone
from decimal import ROUND_DOWN, Decimal

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.games.infrastructure.models import Bet, TrucoMesa
from app.modules.games.shared.betting import parse_bet_amount
from app.modules.games.shared.semillas import (
    generar_client_seed,
    generar_server_seed,
    hashear_seed,
)
from app.modules.games.truco.mano import aplicar_accion, jugador_en_turno
from app.modules.games.truco.partida import Partida
from app.modules.games.truco.reglas import PUNTOS_PARTIDA
from app.modules.users.infrastructure.models import User
from app.modules.wallet.application.balance import credit, debit
from app.modules.wallet.infrastructure.models import Transaction

GAME_ID = "truco_mesa"

ESPERANDO = "esperando"
JUGANDO = "jugando"
TERMINADA = "terminada"

JUGADA = "jugada"
ABANDONO = "abandono"
PLAZO_VENCIDO = "plazo_vencido"

# Lo que se queda la casa del pozo. Los dos jugadores ponen la apuesta y el
# ganador se lleva el resto.
COMISION = Decimal("0.05")

# El mismo minuto y medio que la generala, y la razón por la que no es más
# largo es justamente que el truco tiene más acciones, no menos.
#
# Medido sobre 3000 partidas del bot contra sí mismo: una partida a 30 puntos
# son 168 acciones (mediana 169, p99 209), unas 75 por jugador, contra las 56
# de una partida de generala. O sea 2,7 veces más veces que hay que esperar al
# rival. El plazo multiplica por ahí: a 90 segundos, una mesa jugada siempre al
# límite dura 4,2 horas; a dos minutos pasaría a 5,6. Alargarlo no sale gratis,
# porque mientras tanto la plata de los dos está adentro y el único modo de
# irse es entregar la mesa.
#
# Y no hace falta: lo que una acción de truco pide pensar es menos, no más.
# Medido sobre las mismas partidas, el 60,5% de las acciones es tirar una de
# las tres cartas, y la mediana de opciones legales es 5 (máximo 8). El 39,5%
# restante son cantos y respuestas —ahí sí se piensa—, pero decidir entre
# querer y no querer un envido con 90 segundos encima sobra; una tirada de
# generala, que es elegir qué dados guardar y en qué casillero anotar, es una
# decisión más grande y le alcanza con los mismos 90.
#
# Si en producción se ve gente perdiendo mesas por el reloj, el número a mover
# es este y está medido contra qué.
PLAZO_DE_TURNO = timedelta(seconds=90)

APUESTA_MAXIMA = Decimal("500.00")
CENTAVOS = Decimal("0.01")


# ------------------------------ consultas ------------------------------

async def mesa_del_jugador(db: AsyncSession, user_id: int):
    """La mesa en la que está sentado, si tiene alguna sin terminar."""
    return await db.scalar(
        select(TrucoMesa)
        .where(
            TrucoMesa.estado != TERMINADA,
            or_(TrucoMesa.jugador_0_id == user_id, TrucoMesa.jugador_1_id == user_id),
        )
        .limit(1)
    )


async def listar_mesas(db: AsyncSession, user_id: int) -> list:
    """Las mesas esperando rival, más la propia si está jugando."""
    filas = (
        await db.scalars(
            select(TrucoMesa)
            .where(TrucoMesa.estado != TERMINADA)
            .order_by(TrucoMesa.id.desc())
            .limit(50)
        )
    ).all()

    nombres = await _nombres(db, filas)

    return [
        {
            "id": fila.id,
            "apuesta": str(fila.apuesta),
            "con_flor": bool(fila.con_flor),
            "estado": fila.estado,
            "creador": nombres.get(fila.jugador_0_id, "?"),
            "rival": nombres.get(fila.jugador_1_id),
            "soy_parte": user_id in (fila.jugador_0_id, fila.jugador_1_id),
            "puedo_sentarme": fila.estado == ESPERANDO and fila.jugador_0_id != user_id,
        }
        for fila in filas
    ]


async def _nombres(db: AsyncSession, filas) -> dict:
    ids = {fila.jugador_0_id for fila in filas} | {
        fila.jugador_1_id for fila in filas if fila.jugador_1_id
    }
    if not ids:
        return {}

    usuarios = (await db.scalars(select(User).where(User.id.in_(ids)))).all()
    return {usuario.id: usuario.username for usuario in usuarios}


def asiento_de(fila: TrucoMesa, user_id: int) -> int:
    if fila.jugador_0_id == user_id:
        return 0

    if fila.jugador_1_id == user_id:
        return 1

    raise HTTPException(status_code=403, detail="No estás sentado en esta mesa")


def reconstruir(fila: TrucoMesa) -> Partida:
    partida = Partida(
        fila.server_seed,
        fila.client_seed,
        fila.nonce_base,
        mano_inicial=0,
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


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _vence(fila: TrucoMesa) -> datetime:
    """Cuándo se le vence el plazo al que tiene que hablar."""
    desde = fila.ultima_accion or fila.created_at or _ahora()
    if desde.tzinfo is None:
        desde = desde.replace(tzinfo=timezone.utc)

    return desde + PLAZO_DE_TURNO


def _segundos_restantes(fila: TrucoMesa) -> int:
    return max(0, int((_vence(fila) - _ahora()).total_seconds()))


# ------------------------------ acciones ------------------------------

async def crear_mesa(
    db: AsyncSession, user_id: int, monto_crudo, con_flor: bool = False
) -> dict:
    if await mesa_del_jugador(db, user_id) is not None:
        raise HTTPException(status_code=400, detail="Ya estás en una mesa")

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
            description="Truco mesa",
        )
    )

    server_seed = generar_server_seed()
    fila = TrucoMesa(
        jugador_0_id=user_id,
        apuesta=apuesta,
        con_flor=con_flor,
        estado=ESPERANDO,
        server_seed=server_seed,
        server_seed_hash=hashear_seed(server_seed),
        client_seed=generar_client_seed(),
        nonce_base=0,
        acciones=[],
    )
    db.add(fila)
    await db.commit()
    await db.refresh(fila)

    return await ver_mesa(db, user_id, fila.id)


async def sentarse(db: AsyncSession, user_id: int, mesa_id: int) -> dict:
    if await mesa_del_jugador(db, user_id) is not None:
        raise HTTPException(status_code=400, detail="Ya estás en una mesa")

    fila = await db.get(TrucoMesa, mesa_id, with_for_update=True)
    if fila is None:
        raise HTTPException(status_code=404, detail="Esa mesa no existe")

    if fila.estado != ESPERANDO or fila.jugador_1_id is not None:
        raise HTTPException(status_code=400, detail="Esa mesa ya está completa")

    if fila.jugador_0_id == user_id:
        raise HTTPException(status_code=400, detail="Es tu propia mesa")

    if not await debit(db, user_id, Decimal(fila.apuesta)):
        raise HTTPException(status_code=400, detail="Saldo insuficiente")

    db.add(
        Transaction(
            user_id=user_id,
            amount=Decimal(fila.apuesta),
            transaction_type="BET",
            description="Truco mesa",
        )
    )

    fila.jugador_1_id = user_id
    fila.estado = JUGANDO
    fila.ultima_accion = _ahora()
    await db.commit()

    return await ver_mesa(db, user_id, mesa_id)


async def ver_mesa(db: AsyncSession, user_id: int, mesa_id: int) -> dict:
    fila = await db.get(TrucoMesa, mesa_id)
    if fila is None:
        raise HTTPException(status_code=404, detail="Esa mesa no existe")

    asiento = asiento_de(fila, user_id)
    return await _respuesta(db, fila, asiento)


async def jugar(db: AsyncSession, user_id: int, mesa_id: int, accion: str) -> dict:
    fila = await db.get(TrucoMesa, mesa_id, with_for_update=True)
    if fila is None:
        raise HTTPException(status_code=404, detail="Esa mesa no existe")

    asiento = asiento_de(fila, user_id)

    if fila.estado != JUGANDO:
        raise HTTPException(status_code=400, detail="La mesa no está en juego")

    partida = reconstruir(fila)
    mano = partida.mano_actual

    if jugador_en_turno(mano) != asiento:
        raise HTTPException(status_code=400, detail="No es tu turno")

    if accion not in mano.acciones(asiento):
        raise HTTPException(status_code=400, detail="Esa acción no se puede ahora")

    # Hablar tarde no se rechaza. El plazo funciona como el reloj del ajedrez:
    # vencido habilita al rival a reclamar, pero mientras no reclame la partida
    # sigue. Bloquear la jugada tardía dejaría la mesa trabada para siempre si
    # el rival se fue y nunca reclama, con la plata de los dos adentro.
    acciones = list(fila.acciones)
    aplicar_accion(mano, asiento, accion)
    acciones.append({"jugador": asiento, "accion": accion})

    if mano.terminada:
        partida.cerrar_mano()
        if not partida.terminada:
            partida.nueva_mano()

    fila.acciones = acciones
    fila.ultima_accion = _ahora()

    if partida.terminada:
        await _liquidar(db, fila, partida.ganador, partida, JUGADA)

    await db.commit()
    await db.refresh(fila)

    return await _respuesta(db, fila, asiento)


async def abandonar(db: AsyncSession, user_id: int, mesa_id: int) -> dict:
    """Irse de la mesa. Si nadie se sentó, se devuelve la apuesta."""
    fila = await db.get(TrucoMesa, mesa_id, with_for_update=True)
    if fila is None:
        raise HTTPException(status_code=404, detail="Esa mesa no existe")

    asiento = asiento_de(fila, user_id)

    if fila.estado == TERMINADA:
        raise HTTPException(status_code=400, detail="Esa mesa ya terminó")

    if fila.estado == ESPERANDO:
        await credit(db, user_id, Decimal(fila.apuesta))
        db.add(
            Transaction(
                user_id=user_id,
                amount=Decimal(fila.apuesta),
                transaction_type="REFUND",
                description="Truco mesa cancelada",
            )
        )
        fila.estado = TERMINADA
        fila.motivo = ABANDONO
        await db.commit()
        await db.refresh(fila)
        return await _respuesta(db, fila, asiento)

    # Abandonar con la mesa en juego es entregarla, sin importar el puntaje.
    await _liquidar(db, fila, 1 - asiento, reconstruir(fila), ABANDONO)
    await db.commit()
    await db.refresh(fila)

    return await _respuesta(db, fila, asiento)


async def reclamar(db: AsyncSession, user_id: int, mesa_id: int) -> dict:
    """Llevarse la mesa porque al rival se le venció el plazo del turno.

    Esto es lo que hace que colgarse no sea una jugada. Sólo se puede reclamar
    cuando le toca hablar al otro y el plazo ya pasó: si el que está pensando
    es el que reclama, no hay nada que reclamar.
    """
    fila = await db.get(TrucoMesa, mesa_id, with_for_update=True)
    if fila is None:
        raise HTTPException(status_code=404, detail="Esa mesa no existe")

    asiento = asiento_de(fila, user_id)

    if fila.estado != JUGANDO:
        raise HTTPException(status_code=400, detail="La mesa no está en juego")

    partida = reconstruir(fila)

    if partida.terminada:
        # No debería pasar —jugar() liquida en cuanto el motor cierra— pero si
        # pasara, vale el resultado de la partida y no el reclamo.
        await _liquidar(db, fila, partida.ganador, partida, JUGADA)
        await db.commit()
        await db.refresh(fila)
        return await _respuesta(db, fila, asiento)

    if jugador_en_turno(partida.mano_actual) == asiento:
        raise HTTPException(status_code=400, detail="El turno es tuyo, jugá")

    if _segundos_restantes(fila) > 0:
        raise HTTPException(
            status_code=400, detail="Todavía está en plazo para jugar"
        )

    await _liquidar(db, fila, asiento, partida, PLAZO_VENCIDO)
    await db.commit()
    await db.refresh(fila)

    return await _respuesta(db, fila, asiento)


async def _liquidar(
    db: AsyncSession,
    fila: TrucoMesa,
    ganador: int,
    partida,
    motivo: str = JUGADA,
) -> None:
    pozo = Decimal(fila.apuesta) * 2
    comision = (pozo * COMISION).quantize(CENTAVOS, rounding=ROUND_DOWN)
    premio = pozo - comision

    fila.estado = TERMINADA
    fila.ganador = ganador
    fila.premio = premio
    fila.comision = comision
    fila.motivo = motivo

    ganador_id = fila.jugador_0_id if ganador == 0 else fila.jugador_1_id

    if ganador_id is not None and await credit(db, ganador_id, premio):
        db.add(
            Transaction(
                user_id=ganador_id,
                amount=premio,
                transaction_type="PAYOUT",
                description="Truco mesa",
            )
        )

    for asiento, jugador_id in ((0, fila.jugador_0_id), (1, fila.jugador_1_id)):
        if jugador_id is None:
            continue

        db.add(
            Bet(
                user_id=jugador_id,
                game_id=GAME_ID,
                bet_amount=Decimal(fila.apuesta),
                payout=premio if asiento == ganador else Decimal("0.00"),
                result_data={
                    "mesa_id": fila.id,
                    "asiento": asiento,
                    "puntos": list(partida.puntos),
                    "ganador": ganador,
                    "motivo": motivo,
                    "comision": str(comision),
                    "server_seed": fila.server_seed,
                    "server_seed_hash": fila.server_seed_hash,
                    "client_seed": fila.client_seed,
                },
            )
        )


async def _respuesta(db: AsyncSession, fila: TrucoMesa, asiento: int) -> dict:
    nombres = await _nombres(db, [fila])

    respuesta = {
        "mesa_id": fila.id,
        "estado": fila.estado,
        "asiento": asiento,
        "apuesta": str(fila.apuesta),
        "con_flor": bool(fila.con_flor),
        "pozo": str(Decimal(fila.apuesta) * 2),
        "comision": str(COMISION),
        "premio": str(fila.premio),
        "motivo": fila.motivo,
        "jugadores": [
            nombres.get(fila.jugador_0_id, "?"),
            nombres.get(fila.jugador_1_id),
        ],
        "plazo_de_turno": int(PLAZO_DE_TURNO.total_seconds()),
        "server_seed_hash": fila.server_seed_hash,
        "client_seed": fila.client_seed,
        "server_seed": fila.server_seed if fila.estado == TERMINADA else None,
        "acciones_jugadas": len(fila.acciones),
    }

    if fila.estado == ESPERANDO:
        respuesta["mano"] = None
        respuesta["puntos"] = [0, 0]
        respuesta["terminada"] = False
        respuesta["ganador"] = None
        respuesta["me_toca"] = False
        respuesta["segundos_restantes"] = None
        respuesta["puedo_reclamar"] = False
        return respuesta

    partida = reconstruir(fila)
    respuesta.update(partida.estado(para=asiento))
    respuesta["terminada"] = fila.estado == TERMINADA
    respuesta["ganador"] = fila.ganador

    en_juego = fila.estado == JUGANDO and not partida.terminada
    me_toca = en_juego and jugador_en_turno(partida.mano_actual) == asiento
    restantes = _segundos_restantes(fila) if en_juego else None

    respuesta["me_toca"] = me_toca
    respuesta["segundos_restantes"] = restantes
    respuesta["puedo_reclamar"] = bool(en_juego and not me_toca and restantes == 0)

    return respuesta
