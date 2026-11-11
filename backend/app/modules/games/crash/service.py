import asyncio
import json
import os
import socket
import time
import uuid
from decimal import ROUND_DOWN, Decimal
from typing import List, Optional

from fastapi import WebSocket

from app.modules.games.crash.estado import (
    CANAL_EVENTOS,
    CLAVE_APUESTAS,
    CLAVE_CASHOUTS,
    CLAVE_LIDER,
    CLAVE_NONCE,
    CLAVE_RONDA,
    CLAVE_SECRETO,
    CLAVE_ULTIMO_SEED,
    LUA_APOSTAR,
    LUA_COBRAR,
    LUA_RENOVAR_LIDERAZGO,
    LUA_TOMAR_LIDERAZGO,
    SEGUNDOS_ENTRE_INTENTOS_DE_LIDERAZGO,
    SEGUNDOS_ENTRE_RENOVACIONES,
    TTL_LIDERAZGO_MS,
    armar_estado_publico,
    multiplicador_en,
    tiempo_de_vuelo,
)
from app.modules.games.crash.fairness import (
    CLIENT_SEED_INICIAL,
    calcular_crash_point,
    generar_server_seed,
    hashear_seed,
)
from app.modules.games.infrastructure.models import CrashBet, CrashGameSession
from app.modules.games.shared.betting import parse_bet_amount
from app.modules.wallet.application.balance import credit, debit
from app.modules.wallet.infrastructure.models import Transaction
from app.shared.database import AsyncSessionLocal
from app.shared.redis import get_redis

SEGUNDOS_DE_APUESTAS = 10
SEGUNDOS_ENTRE_RONDAS = 5
INTERVALO_DE_TICK = 0.1
CENTAVOS = Decimal("0.01")


class ConnectionManager:
    """Los WebSockets conectados a este proceso, nada más.

    El estado del juego no vive acá: los eventos llegan por el canal de Redis y
    este manager sólo los reparte a sus propias conexiones.
    """

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        dead_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                dead_connections.append(connection)

        for conn in dead_connections:
            self.disconnect(conn)


class CrashManager:
    """Atiende los WebSockets de este proceso y, si gana el lock, corre el juego.

    Antes esto era un singleton con el estado en memoria: con dos workers había
    dos juegos distintos corriendo en paralelo, cada uno con su multiplicador.
    Ahora la ronda vive en Redis y un solo proceso a la vez la hace avanzar.
    """

    def __init__(self):
        self.connection_manager = ConnectionManager()
        # El sufijo aleatorio evita que un proceso reiniciado con el mismo PID
        # se crea dueño de un lock que ya no es suyo.
        self.identidad = "%s-%s-%s" % (
            socket.gethostname(),
            os.getpid(),
            uuid.uuid4().hex[:8],
        )
        self.tarea_loop: Optional[asyncio.Task] = None
        self.tarea_eventos: Optional[asyncio.Task] = None
        self.ultima_renovacion = 0.0

    def start_loop(self):
        """Arranca las dos tareas del proceso.

        Todos los procesos escuchan eventos; el game loop lo corre el que gane
        el lock, y los demás quedan esperando por si ese se cae.
        """
        if self.tarea_eventos is None:
            self.tarea_eventos = asyncio.create_task(self.escuchar_eventos())
        if self.tarea_loop is None:
            self.tarea_loop = asyncio.create_task(self.correr_game_loop())

    # ------------------------------ estado ------------------------------

    async def current_state(self) -> dict:
        """Estado público de la ronda, para el handshake del WebSocket."""
        redis = get_redis()
        async with redis.pipeline(transaction=False) as pipe:
            pipe.hgetall(CLAVE_RONDA)
            pipe.hgetall(CLAVE_APUESTAS)
            pipe.hgetall(CLAVE_CASHOUTS)
            ronda, apuestas, cashouts = await pipe.execute()

        return armar_estado_publico(ronda, apuestas, cashouts)

    async def publicar_estado(self) -> dict:
        estado = await self.current_state()
        await get_redis().publish(
            CANAL_EVENTOS, json.dumps({"type": "state", "data": estado})
        )
        return estado

    async def escuchar_eventos(self):
        """Reparte a los WebSockets locales lo que publica el líder."""
        while True:
            try:
                pubsub = get_redis().pubsub()
                await pubsub.subscribe(CANAL_EVENTOS)
                async for mensaje in pubsub.listen():
                    if mensaje["type"] == "message":
                        await self.connection_manager.broadcast(json.loads(mensaje["data"]))
            except asyncio.CancelledError:
                raise
            except Exception as e:
                print(f"Error escuchando eventos de Crash: {e}")
                await asyncio.sleep(2)

    # ------------------------------ liderazgo ------------------------------

    async def _tomar_liderazgo(self, redis) -> bool:
        tomado = await redis.eval(
            LUA_TOMAR_LIDERAZGO, 1, CLAVE_LIDER, self.identidad, TTL_LIDERAZGO_MS
        )
        if tomado:
            self.ultima_renovacion = time.monotonic()
        return bool(tomado)

    async def _sostener_liderazgo(self, redis) -> bool:
        """Renueva el lock cada tanto. Devuelve False si lo perdimos."""
        if time.monotonic() - self.ultima_renovacion < SEGUNDOS_ENTRE_RENOVACIONES:
            return True

        renovado = await redis.eval(
            LUA_RENOVAR_LIDERAZGO, 1, CLAVE_LIDER, self.identidad, TTL_LIDERAZGO_MS
        )
        self.ultima_renovacion = time.monotonic()
        return bool(renovado)

    # ------------------------------ el juego ------------------------------

    async def correr_game_loop(self):
        redis = get_redis()
        while True:
            try:
                if await self._tomar_liderazgo(redis):
                    await self._jugar_una_ronda(redis)
                else:
                    await asyncio.sleep(SEGUNDOS_ENTRE_INTENTOS_DE_LIDERAZGO)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                print(f"Error in Crash game loop: {e}")
                await asyncio.sleep(5)

    async def _jugar_una_ronda(self, redis):
        # Si el líder anterior murió a mitad de una ronda, hay que cerrarla antes
        # de abrir otra: esas apuestas ya salieron del saldo de alguien.
        await self._recuperar_ronda_huerfana(redis)

        # El nonce sale de un INCR y el client seed del último seed revelado, no
        # del hash de la ronda en curso: así una ronda abandonada no reinicia la
        # cadena ni repite un número de ronda.
        server_seed = generar_server_seed()
        nonce = await redis.incr(CLAVE_NONCE)
        client_seed = await redis.get(CLAVE_ULTIMO_SEED) or CLIENT_SEED_INICIAL
        crash_point = calcular_crash_point(server_seed, client_seed, nonce)

        await self._abrir_apuestas(redis, server_seed, client_seed, nonce, crash_point)

        if not await self._contar_regresiva(redis):
            return
        if not await self._volar(redis, crash_point):
            return

        await self._explotar(redis, server_seed, crash_point)
        await self._liquidar(redis, server_seed, crash_point)
        await asyncio.sleep(SEGUNDOS_ENTRE_RONDAS)

    async def _abrir_apuestas(self, redis, server_seed, client_seed, nonce, crash_point):
        """El crash point ya está decidido; lo único que se publica es su hash."""
        async with redis.pipeline(transaction=True) as pipe:
            pipe.delete(CLAVE_RONDA, CLAVE_SECRETO, CLAVE_APUESTAS, CLAVE_CASHOUTS)
            pipe.hset(
                CLAVE_RONDA,
                mapping={
                    "nonce": nonce,
                    "fase": "BETTING",
                    "multiplicador": "1.0",
                    "timer": SEGUNDOS_DE_APUESTAS,
                    "server_seed_hash": hashear_seed(server_seed),
                    "client_seed": client_seed,
                },
            )
            pipe.hset(
                CLAVE_SECRETO,
                mapping={"server_seed": server_seed, "crash_point": crash_point},
            )
            await pipe.execute()

        await self.publicar_estado()

    async def _contar_regresiva(self, redis) -> bool:
        for restante in range(SEGUNDOS_DE_APUESTAS - 1, -1, -1):
            await asyncio.sleep(1)

            if not await self._sostener_liderazgo(redis):
                return False

            await redis.hset(CLAVE_RONDA, "timer", restante)
            await self.publicar_estado()

        return True

    async def _volar(self, redis, crash_point: float) -> bool:
        # El arranque lo marca el reloj de Redis para que todos los procesos
        # midan el vuelo contra la misma hora.
        segundos, micros = await redis.time()
        arranque = segundos + micros / 1_000_000
        desfase = arranque - time.time()
        crash_ts = arranque + tiempo_de_vuelo(crash_point)

        # crash_ts tiene que existir antes de que la fase habilite cobrar.
        async with redis.pipeline(transaction=True) as pipe:
            pipe.hset(CLAVE_SECRETO, "crash_ts", crash_ts)
            pipe.hset(
                CLAVE_RONDA,
                mapping={"fase": "IN_PROGRESS", "arranque_ts": arranque, "timer": 0},
            )
            await pipe.execute()

        while True:
            ahora = time.time() + desfase
            if ahora >= crash_ts:
                return True

            if not await self._sostener_liderazgo(redis):
                return False

            await redis.hset(CLAVE_RONDA, "multiplicador", multiplicador_en(ahora, arranque))
            await self.publicar_estado()
            await asyncio.sleep(INTERVALO_DE_TICK)

    async def _explotar(self, redis, server_seed: str, crash_point: float):
        """Recién acá se revelan el crash point y el seed."""
        async with redis.pipeline(transaction=True) as pipe:
            pipe.hset(
                CLAVE_RONDA,
                mapping={
                    "fase": "CRASHED",
                    "multiplicador": crash_point,
                    "crash_point": crash_point,
                    "server_seed": server_seed,
                },
            )
            pipe.set(CLAVE_ULTIMO_SEED, server_seed)
            await pipe.execute()

        await self.publicar_estado()

    async def _recuperar_ronda_huerfana(self, redis):
        """Cierra la ronda que dejó colgada un líder que se murió.

        Las apuestas ya se descontaron del saldo: dejarlas sin liquidar sería
        quedarse con la plata de los jugadores.
        """
        ronda = await redis.hgetall(CLAVE_RONDA)
        fase = ronda.get("fase")

        if not fase or ronda.get("liquidada"):
            return

        if fase == "BETTING":
            # Nunca despegó: se devuelve todo lo apostado.
            apuestas = await redis.hgetall(CLAVE_APUESTAS)
            for user_id, apuesta_cruda in apuestas.items():
                apuesta = json.loads(apuesta_cruda)
                await self._devolver(int(user_id), Decimal(str(apuesta["bet_amount"])))
            await redis.hset(CLAVE_RONDA, "liquidada", 1)
            return

        # Ya estaba en vuelo (o explotada sin liquidar): el crash point y los
        # cashouts quedaron guardados, así que se resuelve igual que siempre.
        secreto = await redis.hgetall(CLAVE_SECRETO)
        server_seed = secreto.get("server_seed", "")
        crash_point = float(secreto.get("crash_point", 1.0))

        if fase != "CRASHED":
            await self._explotar(redis, server_seed, crash_point)

        await self._liquidar(redis, server_seed, crash_point)

    async def _liquidar(self, redis, server_seed: str, crash_point: float):
        """Guarda la ronda y paga a los que llegaron a cobrar."""
        async with redis.pipeline(transaction=False) as pipe:
            pipe.hgetall(CLAVE_RONDA)
            pipe.hgetall(CLAVE_APUESTAS)
            pipe.hgetall(CLAVE_CASHOUTS)
            ronda, apuestas, cashouts = await pipe.execute()

        arranque = float(ronda.get("arranque_ts", 0))

        async with AsyncSessionLocal() as db:
            session = CrashGameSession(
                status="CRASHED",
                crash_point=Decimal(str(crash_point)),
                server_seed=server_seed,
                server_seed_hash=ronda.get("server_seed_hash"),
                client_seed=ronda.get("client_seed"),
                nonce=int(float(ronda.get("nonce", 0))),
            )
            db.add(session)
            await db.commit()
            await db.refresh(session)

            for user_id_crudo, apuesta_cruda in apuestas.items():
                user_id = int(user_id_crudo)
                apuesta = json.loads(apuesta_cruda)
                monto = Decimal(str(apuesta["bet_amount"]))

                cashout_ts = cashouts.get(user_id_crudo)
                multiplicador = None
                payout = Decimal("0.00")

                if cashout_ts is not None:
                    multiplicador = min(multiplicador_en(float(cashout_ts), arranque), crash_point)
                    payout = (monto * Decimal(str(multiplicador))).quantize(
                        CENTAVOS, rounding=ROUND_DOWN
                    )

                db.add(
                    CrashBet(
                        session_id=session.id,
                        user_id=user_id,
                        bet_amount=monto,
                        cashout_multiplier=(
                            Decimal(str(multiplicador)) if multiplicador is not None else None
                        ),
                        payout=payout,
                    )
                )

                if payout > 0 and await credit(db, user_id, payout):
                    db.add(
                        Transaction(
                            user_id=user_id,
                            amount=payout,
                            transaction_type="CASHOUT",
                            description="Crash Payout",
                        )
                    )

            await db.commit()

        # Marca de liquidada: si el líder se cae justo acá, el que lo reemplaza
        # sabe que esta ronda ya se pagó y no la paga dos veces.
        await redis.hset(CLAVE_RONDA, "liquidada", 1)

    # ------------------------------ jugadores ------------------------------

    async def place_bet(self, user_id: int, username: str, raw_amount) -> bool:
        redis = get_redis()
        ronda = await redis.hgetall(CLAVE_RONDA)

        if ronda.get("fase") != "BETTING":
            return False

        # El monto llega del cliente por WebSocket: se valida acá porque no pasa
        # por ningún schema. Un monto negativo acreditaba saldo en vez de restarlo.
        amount = parse_bet_amount(raw_amount)
        if amount is None:
            return False

        async with AsyncSessionLocal() as db:
            if not await debit(db, user_id, amount):
                return False

            db.add(
                Transaction(
                    user_id=user_id,
                    amount=amount,
                    transaction_type="BET",
                    description="Crash Bet",
                )
            )
            await db.commit()

        apuesta = json.dumps(
            {"user_id": user_id, "username": username, "bet_amount": float(amount)}
        )
        aceptada = await redis.eval(
            LUA_APOSTAR,
            2,
            CLAVE_RONDA,
            CLAVE_APUESTAS,
            ronda.get("nonce", ""),
            str(user_id),
            apuesta,
        )

        if not aceptada:
            # La ronda arrancó o el jugador ya tenía una apuesta: se devuelve.
            await self._devolver(user_id, amount)
            return False

        await self.publicar_estado()
        return True

    async def _devolver(self, user_id: int, amount: Decimal):
        async with AsyncSessionLocal() as db:
            if await credit(db, user_id, amount):
                db.add(
                    Transaction(
                        user_id=user_id,
                        amount=amount,
                        transaction_type="REFUND",
                        description="Crash Bet Refund",
                    )
                )
                await db.commit()

    async def cash_out(self, user_id: int) -> bool:
        """El multiplicador lo fija el reloj de Redis, no el del worker."""
        momento = await get_redis().eval(
            LUA_COBRAR,
            4,
            CLAVE_RONDA,
            CLAVE_APUESTAS,
            CLAVE_SECRETO,
            CLAVE_CASHOUTS,
            str(user_id),
        )

        if not momento:
            return False

        await self.publicar_estado()
        return True


crash_manager = CrashManager()
