"""Mesas de generala entre dos jugadores.

Reusa el motor entero de la partida contra la casa: las mismas reglas, el mismo
flujo de dados verificable y el mismo truco de guardar las acciones en vez del
estado. Lo que cambia es que los dos asientos son personas, así que nadie
adelanta el juego: cada uno juega cuando le toca.

Por qué esto importa más en la generala que en el truco
-------------------------------------------------------
La generala contra la casa tiene un problema que no se arregla con el
multiplicador: con pago binario por ganar o perder, la diferencia de retorno
entre un casual y un experto es exactamente la diferencia de habilidad. Medido,
al que juega al máximo le vuelve el 93,9% y al que juega como en una mesa de
casa el 68,6%, y mover el multiplicador los corre a los dos juntos.

Acá eso desaparece de raíz. La casa no juega: pone la mesa y cobra una comisión
sobre el pozo, como en las mesas de poker. La ventaja no depende de qué tan
bien juegue nadie, y los dos jugadores enfrentan a alguien de su nivel en vez
de a un bot que calcula exacto.

El plazo de turno
-----------------
Las mesas de truco no tienen plazo y eso es un agujero: el que va perdiendo
nunca está obligado a perder, le alcanza con dejar de jugar. El rival sólo
puede abandonar, y abandonar es entregar la mesa. O sea que colgarse es
estrictamente mejor que perder.

Acá el turno tiene plazo. Si el que tiene que jugar no juega en
`PLAZO_DE_TURNO`, el rival reclama la mesa y se la lleva. No hace falta ningún
proceso de fondo: el plazo se mira cuando alguien pregunta por la mesa, que es
cada un par de segundos mientras hay alguien mirando.

Sin WebSocket: el cliente consulta el estado cada par de segundos. Para un
juego por turnos alcanza. Si hiciera falta que sea instantáneo, el canal de
Redis que usa crash ya está.
"""

from datetime import datetime, timedelta, timezone
from decimal import ROUND_DOWN, Decimal

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.games.generala.partida import Partida, reconstruir_desde
from app.modules.games.generala.turno import aplicar_accion
from app.modules.games.infrastructure.models import Bet, GeneralaMesa
from app.modules.games.shared.betting import parse_bet_amount
from app.modules.games.shared.mezcla import flujo_de_bytes, indice_uniforme
from app.modules.games.shared.semillas import (
    generar_client_seed,
    generar_server_seed,
    hashear_seed,
)
from app.modules.users.infrastructure.models import User
from app.modules.wallet.application.balance import credit, debit
from app.modules.wallet.infrastructure.models import Transaction

GAME_ID = "generala_mesa"

ESPERANDO = "esperando"
JUGANDO = "jugando"
TERMINADA = "terminada"

JUGADA = "jugada"
ABANDONO = "abandono"
PLAZO_VENCIDO = "plazo_vencido"

# Lo que se queda la casa del pozo. Los dos ponen la apuesta y el ganador se
# lleva el resto. Es la única forma en que la casa gana plata acá, y no depende
# de quién juegue mejor.
COMISION = Decimal("0.05")

# Un turno de generala es tirar y anotar: con un minuto y medio sobra de sobra
# incluso pensando. Es largo a propósito, porque el costo de equivocarse para
# abajo es sacarle la mesa a alguien que estaba decidiendo.
PLAZO_DE_TURNO = timedelta(seconds=90)

APUESTA_MAXIMA = Decimal("500.00")
CENTAVOS = Decimal("0.01")


# ------------------------------ quién empieza ------------------------------

def empieza_segun_seed(server_seed: str, client_seed: str, nonce: int) -> int:
    """El asiento que arranca, sacado del seed.

    Empezar vale poco —medido, 0,3 puntos de porcentaje— pero vale algo, y acá
    no hay forma de alternarlo porque cada mesa es una sola partida. Dárselo al
    que crea la mesa sería regalárselo; dárselo al que se sienta sería premiar
    esperar. Sale del seed, que no lo controla ninguno de los dos, y queda
    verificable como todo el resto.

    Usa un flujo aparte: el prefijo lo separa del de los dados, así derivar
    esto no desplaza ni un dado de la partida.
    """
    flujo = flujo_de_bytes(server_seed, "empieza:%s" % client_seed, nonce)
    return indice_uniforme(flujo, 2)


# ------------------------------ consultas ------------------------------

async def mesa_del_jugador(db: AsyncSession, user_id: int):
    """La mesa en la que está sentado, si tiene alguna sin terminar."""
    return await db.scalar(
        select(GeneralaMesa)
        .where(
            GeneralaMesa.estado != TERMINADA,
            or_(
                GeneralaMesa.jugador_0_id == user_id,
                GeneralaMesa.jugador_1_id == user_id,
            ),
        )
        .limit(1)
    )


async def listar_mesas(db: AsyncSession, user_id: int) -> list:
    """Las mesas esperando rival, más la propia si está jugando."""
    filas = (
        await db.scalars(
            select(GeneralaMesa)
            .where(GeneralaMesa.estado != TERMINADA)
            .order_by(GeneralaMesa.id.desc())
            .limit(50)
        )
    ).all()

    nombres = await _nombres(db, filas)

    return [
        {
            "id": fila.id,
            "apuesta": str(fila.apuesta),
            "pozo": str(Decimal(fila.apuesta) * 2),
            "estado": fila.estado,
            "creador": nombres.get(fila.jugador_0_id, "?"),
            "rival": nombres.get(fila.jugador_1_id),
            "soy_parte": user_id in (fila.jugador_0_id, fila.jugador_1_id),
            "puedo_sentarme": (
                fila.estado == ESPERANDO and fila.jugador_0_id != user_id
            ),
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


def asiento_de(fila: GeneralaMesa, user_id: int) -> int:
    if fila.jugador_0_id == user_id:
        return 0

    if fila.jugador_1_id == user_id:
        return 1

    raise HTTPException(status_code=403, detail="No estás sentado en esta mesa")


def reconstruir(fila: GeneralaMesa) -> Partida:
    """Rehace la partida de la mesa desde las acciones guardadas."""
    return reconstruir_desde(
        fila.server_seed,
        fila.client_seed,
        fila.nonce,
        fila.empieza,
        fila.acciones,
    )


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _vence(fila: GeneralaMesa) -> datetime:
    """Cuándo se le vence el plazo al que tiene que jugar."""
    desde = fila.ultima_accion or fila.created_at or _ahora()
    if desde.tzinfo is None:
        desde = desde.replace(tzinfo=timezone.utc)

    return desde + PLAZO_DE_TURNO


def _segundos_restantes(fila: GeneralaMesa) -> int:
    return max(0, int((_vence(fila) - _ahora()).total_seconds()))


# ------------------------------ acciones ------------------------------

async def crear_mesa(db: AsyncSession, user_id: int, monto_crudo) -> dict:
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
            description="Generala mesa",
        )
    )

    server_seed = generar_server_seed()
    client_seed = generar_client_seed()

    fila = GeneralaMesa(
        jugador_0_id=user_id,
        apuesta=apuesta,
        estado=ESPERANDO,
        server_seed=server_seed,
        server_seed_hash=hashear_seed(server_seed),
        client_seed=client_seed,
        nonce=0,
        empieza=empieza_segun_seed(server_seed, client_seed, 0),
        acciones=[],
    )
    db.add(fila)

    try:
        await db.commit()
    except IntegrityError:
        # Dos "crear mesa" simultáneos: el índice único deja una sola abierta
        # y la apuesta del pedido que perdió vuelve.
        await db.rollback()
        await credit(db, user_id, apuesta)
        await db.commit()
        raise HTTPException(status_code=400, detail="Ya estás en una mesa")

    await db.refresh(fila)

    return await ver_mesa(db, user_id, fila.id)


async def sentarse(db: AsyncSession, user_id: int, mesa_id: int) -> dict:
    if await mesa_del_jugador(db, user_id) is not None:
        raise HTTPException(status_code=400, detail="Ya estás en una mesa")

    fila = await db.get(GeneralaMesa, mesa_id, with_for_update=True)
    if fila is None:
        raise HTTPException(status_code=404, detail="Esa mesa no existe")

    if fila.estado != ESPERANDO or fila.jugador_1_id is not None:
        raise HTTPException(status_code=400, detail="Esa mesa ya está completa")

    if fila.jugador_0_id == user_id:
        raise HTTPException(status_code=400, detail="Es tu propia mesa")

    apuesta = Decimal(fila.apuesta)

    if not await debit(db, user_id, apuesta):
        raise HTTPException(status_code=400, detail="Saldo insuficiente")

    db.add(
        Transaction(
            user_id=user_id,
            amount=apuesta,
            transaction_type="BET",
            description="Generala mesa",
        )
    )

    fila.jugador_1_id = user_id
    fila.estado = JUGANDO
    fila.ultima_accion = _ahora()

    # Generala servida en la primera tirada: pasa una vez cada 1296 y termina
    # la partida antes de que nadie haya tocado nada. Hay que liquidarla acá.
    partida = reconstruir(fila)
    if partida.terminada:
        await _liquidar(db, fila, partida.ganador, partida, JUGADA)

    try:
        await db.commit()
    except IntegrityError:
        # Sentarse en dos mesas a la vez. Igual que al crear: vuelve la apuesta.
        await db.rollback()
        await credit(db, user_id, apuesta)
        await db.commit()
        raise HTTPException(status_code=400, detail="Ya estás en una mesa")

    return await ver_mesa(db, user_id, mesa_id)


async def ver_mesa(db: AsyncSession, user_id: int, mesa_id: int) -> dict:
    fila = await db.get(GeneralaMesa, mesa_id)
    if fila is None:
        raise HTTPException(status_code=404, detail="Esa mesa no existe")

    asiento = asiento_de(fila, user_id)
    return await _respuesta(db, fila, asiento)


async def jugar(db: AsyncSession, user_id: int, mesa_id: int, accion: str) -> dict:
    fila = await db.get(GeneralaMesa, mesa_id, with_for_update=True)
    if fila is None:
        raise HTTPException(status_code=404, detail="Esa mesa no existe")

    asiento = asiento_de(fila, user_id)

    if fila.estado != JUGANDO:
        raise HTTPException(status_code=400, detail="La mesa no está en juego")

    partida = reconstruir(fila)

    if partida.terminada:
        raise HTTPException(status_code=400, detail="La partida ya terminó")

    if partida.en_turno != asiento:
        raise HTTPException(status_code=400, detail="No es tu turno")

    # Jugar tarde no se rechaza. El plazo funciona como el reloj del ajedrez:
    # vencido habilita al rival a reclamar, pero mientras no reclame la partida
    # sigue. Bloquear la jugada dejaría la mesa trabada para siempre si el
    # rival se fue y nunca reclama, con la plata de los dos adentro.
    acciones = list(fila.acciones)

    try:
        aplicar_accion(partida.turno, accion)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    acciones.append({"jugador": asiento, "accion": accion})

    if partida.turno.terminado:
        partida.cerrar_turno()

    fila.acciones = acciones
    fila.ultima_accion = _ahora()

    if partida.terminada:
        await _liquidar(db, fila, partida.ganador, partida, JUGADA)

    await db.commit()
    await db.refresh(fila)

    return await _respuesta(db, fila, asiento)


async def abandonar(db: AsyncSession, user_id: int, mesa_id: int) -> dict:
    """Irse de la mesa. Si nadie se sentó, se devuelve la apuesta."""
    fila = await db.get(GeneralaMesa, mesa_id, with_for_update=True)
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
                description="Generala mesa cancelada",
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
    cuando le toca al otro y el plazo ya pasó: si el que está pensando es el
    que reclama, no hay nada que reclamar.
    """
    fila = await db.get(GeneralaMesa, mesa_id, with_for_update=True)
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

    if partida.en_turno == asiento:
        raise HTTPException(status_code=400, detail="El turno es tuyo, jugá")

    if _segundos_restantes(fila) > 0:
        raise HTTPException(
            status_code=400, detail="Todavía está en plazo para jugar"
        )

    await _liquidar(db, fila, asiento, partida, PLAZO_VENCIDO)
    await db.commit()
    await db.refresh(fila)

    return await _respuesta(db, fila, asiento)


# ------------------------------ la plata ------------------------------

async def _liquidar(
    db: AsyncSession,
    fila: GeneralaMesa,
    ganador,
    partida: Partida,
    motivo: str,
) -> None:
    """Cierra la mesa y reparte el pozo. `ganador` None es empate.

    El empate en la generala pasa cerca de una vez cada cien partidas, así que
    no es un caso de manual. Acá vuelve la apuesta a cada uno y la casa no
    cobra comisión: cobrarla sería quedarse con plata de una mesa que no
    decidió nada.
    """
    pozo = Decimal(fila.apuesta) * 2

    fila.estado = TERMINADA
    fila.ganador = ganador
    fila.motivo = motivo

    if ganador is None:
        fila.comision = Decimal("0.00")
        fila.premio = Decimal(fila.apuesta)

        for jugador_id in (fila.jugador_0_id, fila.jugador_1_id):
            if jugador_id is None:
                continue

            if await credit(db, jugador_id, Decimal(fila.apuesta)):
                db.add(
                    Transaction(
                        user_id=jugador_id,
                        amount=Decimal(fila.apuesta),
                        transaction_type="REFUND",
                        description="Generala mesa empatada",
                    )
                )
    else:
        comision = (pozo * COMISION).quantize(CENTAVOS, rounding=ROUND_DOWN)
        premio = pozo - comision

        fila.comision = comision
        fila.premio = premio

        ganador_id = fila.jugador_0_id if ganador == 0 else fila.jugador_1_id

        if ganador_id is not None and await credit(db, ganador_id, premio):
            db.add(
                Transaction(
                    user_id=ganador_id,
                    amount=premio,
                    transaction_type="PAYOUT",
                    description="Generala mesa",
                )
            )

    for asiento, jugador_id in ((0, fila.jugador_0_id), (1, fila.jugador_1_id)):
        if jugador_id is None:
            continue

        if ganador is None:
            payout = Decimal(fila.apuesta)
        elif asiento == ganador:
            payout = Decimal(fila.premio)
        else:
            payout = Decimal("0.00")

        db.add(
            Bet(
                user_id=jugador_id,
                game_id=GAME_ID,
                bet_amount=Decimal(fila.apuesta),
                payout=payout,
                result_data={
                    "mesa_id": fila.id,
                    "asiento": asiento,
                    "totales": [partida.total(0), partida.total(1)],
                    "ganador": ganador,
                    "motivo": motivo,
                    "generala_servida_de": partida.generala_servida_de,
                    "comision": str(fila.comision),
                    "empieza": fila.empieza,
                    "server_seed": fila.server_seed,
                    "server_seed_hash": fila.server_seed_hash,
                    "client_seed": fila.client_seed,
                    "acciones": fila.acciones,
                },
            )
        )


# ------------------------------ vista ------------------------------

async def _respuesta(db: AsyncSession, fila: GeneralaMesa, asiento: int) -> dict:
    nombres = await _nombres(db, [fila])

    respuesta = {
        "mesa_id": fila.id,
        "estado": fila.estado,
        "asiento": asiento,
        "apuesta": str(fila.apuesta),
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
        "nonce": fila.nonce,
        # El seed se revela recién al cerrar la mesa: antes, el que lo tuviera
        # sabría qué dados vienen.
        "server_seed": fila.server_seed if fila.estado == TERMINADA else None,
        "acciones_jugadas": len(fila.acciones),
    }

    if fila.estado == ESPERANDO:
        respuesta.update(
            {
                "turno": None,
                "planillas": None,
                "totales": [0, 0],
                "en_turno": None,
                "empieza": None,
                "terminada": False,
                "ganador": None,
                "generala_servida_de": None,
                "me_toca": False,
                "segundos_restantes": None,
                "puedo_reclamar": False,
            }
        )
        return respuesta

    partida = reconstruir(fila)
    respuesta.update(partida.estado(para=asiento))
    # El motor saca el turno cuando la partida se cierra sola; la clave tiene
    # que estar igual para que el cliente no tenga que distinguir los casos.
    respuesta.setdefault("turno", None)

    # Quién arranca se publica recién cuando la mesa está en juego: mientras
    # espera rival, el asiento 1 todavía no existe.
    respuesta["empieza"] = fila.empieza
    respuesta["terminada"] = fila.estado == TERMINADA
    respuesta["ganador"] = fila.ganador

    en_juego = fila.estado == JUGANDO and not partida.terminada
    me_toca = en_juego and partida.en_turno == asiento
    restantes = _segundos_restantes(fila) if en_juego else None

    respuesta["me_toca"] = me_toca
    respuesta["segundos_restantes"] = restantes
    respuesta["puedo_reclamar"] = bool(en_juego and not me_toca and restantes == 0)

    return respuesta
