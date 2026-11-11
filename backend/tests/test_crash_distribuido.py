"""Tests del Crash repartido entre procesos.

Necesitan Redis y Postgres. Corren contra una base de Redis aparte para no
pelearse con el juego que esté corriendo:

    docker compose run --rm -e REDIS_URL=redis://redis:6379/15 backend \\
        sh -c "pip install -q pytest pytest-asyncio && pytest tests -q"
"""

import json
import time
from decimal import Decimal

import pytest

try:
    from sqlalchemy import delete, func, select, text

    from app.modules.games.crash.estado import (
        CLAVE_APUESTAS,
        CLAVE_CASHOUTS,
        CLAVE_LIDER,
        CLAVE_RONDA,
        CLAVE_SECRETO,
        multiplicador_en,
    )
    from app.modules.games.crash.service import CrashManager, crash_manager
    from app.modules.games.infrastructure.models import CrashBet, CrashGameSession
    from app.modules.users.infrastructure.models import User
    from app.shared.database import AsyncSessionLocal, engine
    from app.shared.redis import cerrar_redis, get_redis
except Exception as exc:  # pragma: no cover - entorno sin dependencias
    pytest.skip(
        "Requiere sqlalchemy, Redis y Postgres, correr dentro de Docker (%s)" % exc,
        allow_module_level=True,
    )

USERNAME = "test_crash_distribuido"
EMAIL = "test_crash_distribuido@example.test"

# Marca las rondas que fabrica el test, para no dejarlas en el historial
# público: son rondas que no verifican y ensuciarían la auditoría.
SEED_DE_PRUEBA = "seed-secreto"


async def _borrar_usuario_de_prueba(db):
    for tabla in ("transactions", "crash_bets", "bets", "blackjack_games"):
        await db.execute(
            text(
                "DELETE FROM %s WHERE user_id IN "
                "(SELECT id FROM users WHERE username = :username)" % tabla
            ),
            {"username": USERNAME},
        )
    await db.execute(delete(User).where(User.username == USERNAME))

    await db.execute(
        text(
            "DELETE FROM crash_bets WHERE session_id IN "
            "(SELECT id FROM crash_game_sessions WHERE server_seed = :seed)"
        ),
        {"seed": SEED_DE_PRUEBA},
    )
    await db.execute(
        delete(CrashGameSession).where(CrashGameSession.server_seed == SEED_DE_PRUEBA)
    )


@pytest.fixture(autouse=True)
async def _entorno_limpio():
    await engine.dispose()
    await cerrar_redis()

    try:
        redis = get_redis()
        await redis.ping()
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
    except Exception as exc:
        pytest.skip("Redis o Postgres no disponibles: %s" % exc)

    await redis.flushdb()

    yield

    await redis.flushdb()
    async with AsyncSessionLocal() as db:
        await _borrar_usuario_de_prueba(db)
        await db.commit()

    await cerrar_redis()
    await engine.dispose()


async def _usuario_con_saldo(saldo: str) -> int:
    async with AsyncSessionLocal() as db:
        await _borrar_usuario_de_prueba(db)
        user = User(
            username=USERNAME, email=EMAIL, hashed_password="no-importa", balance=Decimal(saldo)
        )
        db.add(user)
        await db.commit()
        return user.id


async def _saldo(user_id: int) -> Decimal:
    async with AsyncSessionLocal() as db:
        return await db.scalar(select(User.balance).where(User.id == user_id))


async def _abrir_ronda_de_apuestas(nonce: int = 1):
    await get_redis().hset(
        CLAVE_RONDA,
        mapping={
            "nonce": nonce,
            "fase": "BETTING",
            "multiplicador": "1.0",
            "timer": 10,
            "server_seed_hash": "hash-publico",
            "client_seed": "cliente",
        },
    )


async def _poner_en_vuelo(crash_point: float = 5.0, segundos_restantes: float = 30.0):
    """Deja la ronda volando, con el crash a futuro para que se pueda cobrar."""
    redis = get_redis()
    ahora = time.time()
    async with redis.pipeline(transaction=True) as pipe:
        pipe.hset(
            CLAVE_SECRETO,
            mapping={
                "server_seed": SEED_DE_PRUEBA,
                "crash_point": crash_point,
                "crash_ts": ahora + segundos_restantes,
            },
        )
        pipe.hset(CLAVE_RONDA, mapping={"fase": "IN_PROGRESS", "arranque_ts": ahora})
        await pipe.execute()


# ------------------------------ liderazgo ------------------------------

async def test_un_solo_proceso_gana_el_liderazgo():
    """Con el estado en memoria, cada worker corría su propio juego."""
    redis = get_redis()
    uno, otro = CrashManager(), CrashManager()

    ganadores = [await uno._tomar_liderazgo(redis), await otro._tomar_liderazgo(redis)]

    assert ganadores.count(True) == 1


async def test_el_lider_puede_encadenar_rondas():
    """Regresión: con SET NX a secas, el líder no podía retomar su propio lock
    al terminar una ronda y perdía el TTL entero esperando."""
    redis = get_redis()
    lider = CrashManager()

    assert await lider._tomar_liderazgo(redis) is True
    assert await lider._tomar_liderazgo(redis) is True


async def test_otro_proceso_toma_el_liderazgo_si_el_lock_caduca():
    redis = get_redis()
    lider, suplente = CrashManager(), CrashManager()

    await lider._tomar_liderazgo(redis)
    assert await suplente._tomar_liderazgo(redis) is False

    await redis.delete(CLAVE_LIDER)  # el TTL expira porque el líder murió

    assert await suplente._tomar_liderazgo(redis) is True


async def test_no_se_renueva_un_lock_ajeno():
    redis = get_redis()
    lider, intruso = CrashManager(), CrashManager()

    await lider._tomar_liderazgo(redis)
    intruso.ultima_renovacion = 0.0

    assert await intruso._sostener_liderazgo(redis) is False
    assert await redis.get(CLAVE_LIDER) == lider.identidad


# ------------------------------ apuestas ------------------------------

async def test_la_apuesta_queda_en_redis_y_descuenta_el_saldo():
    user_id = await _usuario_con_saldo("100.00")
    await _abrir_ronda_de_apuestas()

    assert await crash_manager.place_bet(user_id, USERNAME, 30) is True

    apuesta = json.loads(await get_redis().hget(CLAVE_APUESTAS, str(user_id)))
    assert apuesta["bet_amount"] == 30.0
    assert await _saldo(user_id) == Decimal("70.00")


async def test_no_se_puede_apostar_dos_veces_en_la_misma_ronda():
    """La segunda apuesta se rechaza y la plata vuelve enseguida."""
    user_id = await _usuario_con_saldo("100.00")
    await _abrir_ronda_de_apuestas()

    assert await crash_manager.place_bet(user_id, USERNAME, 30) is True
    assert await crash_manager.place_bet(user_id, USERNAME, 30) is False

    assert await _saldo(user_id) == Decimal("70.00")
    assert await get_redis().hlen(CLAVE_APUESTAS) == 1


async def test_una_apuesta_negativa_no_acredita_saldo():
    """Regresión del exploit de Crash: `balance -= monto` con monto negativo
    sumaba plata, y el chequeo de saldo no cortaba."""
    user_id = await _usuario_con_saldo("50.00")
    await _abrir_ronda_de_apuestas()

    assert await crash_manager.place_bet(user_id, USERNAME, -100000) is False
    assert await _saldo(user_id) == Decimal("50.00")


@pytest.mark.parametrize("monto", [0, "abc", None, float("inf"), 999999])
async def test_los_montos_invalidos_se_rechazan(monto):
    user_id = await _usuario_con_saldo("50.00")
    await _abrir_ronda_de_apuestas()

    assert await crash_manager.place_bet(user_id, USERNAME, monto) is False
    assert await _saldo(user_id) == Decimal("50.00")
    assert await get_redis().hlen(CLAVE_APUESTAS) == 0


async def test_no_se_puede_apostar_sin_saldo():
    user_id = await _usuario_con_saldo("5.00")
    await _abrir_ronda_de_apuestas()

    assert await crash_manager.place_bet(user_id, USERNAME, 20) is False
    assert await _saldo(user_id) == Decimal("5.00")


async def test_no_se_puede_apostar_con_la_ronda_en_vuelo():
    user_id = await _usuario_con_saldo("100.00")
    await _abrir_ronda_de_apuestas()
    await _poner_en_vuelo()

    assert await crash_manager.place_bet(user_id, USERNAME, 30) is False
    assert await _saldo(user_id) == Decimal("100.00")


async def test_la_apuesta_de_una_ronda_vieja_se_rechaza():
    """El nonce viaja en el script: si la ronda cambió, la apuesta no entra."""
    user_id = await _usuario_con_saldo("100.00")
    await _abrir_ronda_de_apuestas(nonce=1)

    redis = get_redis()
    ronda_vieja = await redis.hgetall(CLAVE_RONDA)
    await redis.hset(CLAVE_RONDA, "nonce", 2)  # arrancó otra ronda mientras tanto

    aceptada = await redis.eval(
        "if redis.call('HGET', KEYS[1], 'nonce') ~= ARGV[1] then return 0 end return 1",
        1,
        CLAVE_RONDA,
        ronda_vieja["nonce"],
    )

    assert aceptada == 0


# ------------------------------ cashout ------------------------------

async def test_cobrar_en_vuelo_registra_el_momento():
    user_id = await _usuario_con_saldo("100.00")
    await _abrir_ronda_de_apuestas()
    await crash_manager.place_bet(user_id, USERNAME, 30)
    await _poner_en_vuelo()

    assert await crash_manager.cash_out(user_id) is True
    assert await get_redis().hexists(CLAVE_CASHOUTS, str(user_id)) == 1


async def test_no_se_puede_cobrar_dos_veces():
    user_id = await _usuario_con_saldo("100.00")
    await _abrir_ronda_de_apuestas()
    await crash_manager.place_bet(user_id, USERNAME, 30)
    await _poner_en_vuelo()

    assert await crash_manager.cash_out(user_id) is True
    assert await crash_manager.cash_out(user_id) is False


async def test_no_se_puede_cobrar_despues_del_crash():
    """El reloj lo pone Redis: no sirve que el worker tenga la hora atrasada."""
    user_id = await _usuario_con_saldo("100.00")
    await _abrir_ronda_de_apuestas()
    await crash_manager.place_bet(user_id, USERNAME, 30)
    await _poner_en_vuelo(segundos_restantes=-1.0)

    assert await crash_manager.cash_out(user_id) is False
    assert await get_redis().hexists(CLAVE_CASHOUTS, str(user_id)) == 0


async def test_no_se_puede_cobrar_sin_haber_apostado():
    user_id = await _usuario_con_saldo("100.00")
    await _abrir_ronda_de_apuestas()
    await _poner_en_vuelo()

    assert await crash_manager.cash_out(user_id) is False


# ------------------------ rondas huérfanas ------------------------

async def test_una_ronda_abandonada_en_apuestas_devuelve_la_plata():
    """Si el líder muere antes de despegar, nadie jugó: se devuelve todo."""
    user_id = await _usuario_con_saldo("100.00")
    await _abrir_ronda_de_apuestas()
    await crash_manager.place_bet(user_id, USERNAME, 30)
    assert await _saldo(user_id) == Decimal("70.00")

    await crash_manager._recuperar_ronda_huerfana(get_redis())

    assert await _saldo(user_id) == Decimal("100.00")


async def test_una_ronda_abandonada_en_vuelo_se_liquida():
    """El crash point y los cashouts están en Redis: el que reemplaza al líder
    puede cerrarla igual, sin quedarse con la plata."""
    user_id = await _usuario_con_saldo("100.00")
    await _abrir_ronda_de_apuestas()
    await crash_manager.place_bet(user_id, USERNAME, 30)
    await _poner_en_vuelo(crash_point=5.0)
    await crash_manager.cash_out(user_id)

    async with AsyncSessionLocal() as db:
        rondas_antes = await db.scalar(select(func.count()).select_from(CrashGameSession))

    await crash_manager._recuperar_ronda_huerfana(get_redis())

    async with AsyncSessionLocal() as db:
        rondas_despues = await db.scalar(select(func.count()).select_from(CrashGameSession))
        apuesta = await db.scalar(
            select(CrashBet).where(CrashBet.user_id == user_id).limit(1)
        )

    assert rondas_despues == rondas_antes + 1
    assert apuesta is not None
    assert apuesta.payout > 0
    assert await _saldo(user_id) > Decimal("70.00")


async def test_una_ronda_liquidada_no_se_paga_dos_veces():
    user_id = await _usuario_con_saldo("100.00")
    await _abrir_ronda_de_apuestas()
    await crash_manager.place_bet(user_id, USERNAME, 30)
    await _poner_en_vuelo(crash_point=5.0)
    await crash_manager.cash_out(user_id)

    await crash_manager._recuperar_ronda_huerfana(get_redis())
    saldo_tras_liquidar = await _saldo(user_id)

    await crash_manager._recuperar_ronda_huerfana(get_redis())

    assert await _saldo(user_id) == saldo_tras_liquidar


# ------------------------------ estado público ------------------------------

async def test_el_server_seed_no_se_filtra_antes_del_crash():
    """Si el seed viajara antes de tiempo, cualquiera calcularía el crash point
    de la ronda en curso y cobraría justo antes."""
    await _abrir_ronda_de_apuestas()
    await _poner_en_vuelo()

    estado = await crash_manager.current_state()

    assert estado["server_seed"] is None
    assert estado["crash_point"] is None
    assert estado["server_seed_hash"] == "hash-publico"


async def test_el_seed_se_revela_al_explotar():
    await _abrir_ronda_de_apuestas()
    await _poner_en_vuelo()

    await crash_manager._explotar(get_redis(), SEED_DE_PRUEBA, 5.0)
    estado = await crash_manager.current_state()

    assert estado["server_seed"] == SEED_DE_PRUEBA
    assert estado["crash_point"] == 5.0
    assert estado["status"] == "CRASHED"


async def test_el_estado_publico_conserva_el_contrato_del_frontend():
    user_id = await _usuario_con_saldo("100.00")
    await _abrir_ronda_de_apuestas()
    await crash_manager.place_bet(user_id, USERNAME, 30)

    estado = await crash_manager.current_state()

    assert set(estado) >= {"status", "multiplier", "timer", "bets"}
    assert estado["status"] == "BETTING"
    assert isinstance(estado["multiplier"], float)
    assert estado["bets"][0]["username"] == USERNAME
    assert estado["bets"][0]["bet_amount"] == 30.0
    assert estado["bets"][0]["cashout_multiplier"] is None


async def test_el_multiplicador_del_cashout_sale_del_reloj_compartido():
    """Se deriva del timestamp que grabó Redis, no de lo que vio cada worker."""
    arranque = 1_000_000.0

    assert multiplicador_en(arranque, arranque) == 1.00
    assert multiplicador_en(arranque + 10, arranque) == 1.82  # exp(0.6) truncado
    assert multiplicador_en(arranque - 5, arranque) == 1.00
