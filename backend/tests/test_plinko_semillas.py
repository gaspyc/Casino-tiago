"""Ciclo de vida de la semilla de Plinko y el saldo de cada bola.

Necesitan Postgres, así que corren dentro del contenedor.
"""

import asyncio
from decimal import Decimal

import pytest

try:
    from sqlalchemy import delete, select, text

    from app.modules.games.infrastructure.models import GameSeed
    from app.modules.games.plinko.fairness import derivar_camino, hashear_seed
    from app.modules.games.plinko.schemas import PlinkoBetCreate
    from app.modules.games.plinko.service import (
        GAME_ID,
        describir_semilla,
        obtener_semilla_activa,
        play_plinko_service,
        rotar_semilla,
    )
    from app.modules.users.infrastructure.models import User
    from app.shared.database import AsyncSessionLocal, engine
except Exception as exc:  # pragma: no cover - entorno sin dependencias
    pytest.skip(
        "Requiere sqlalchemy y Postgres, correr dentro de Docker (%s)" % exc,
        allow_module_level=True,
    )

USERNAME = "test_plinko_semillas"
EMAIL = "test_plinko_semillas@example.test"


async def _borrar_usuario_de_prueba(db):
    for tabla in ("transactions", "bets", "game_seeds", "crash_bets", "blackjack_games"):
        await db.execute(
            text(
                "DELETE FROM %s WHERE user_id IN "
                "(SELECT id FROM users WHERE username = :username)" % tabla
            ),
            {"username": USERNAME},
        )
    await db.execute(delete(User).where(User.username == USERNAME))


@pytest.fixture(autouse=True)
async def _entorno_limpio():
    await engine.dispose()

    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
    except Exception as exc:
        pytest.skip("Postgres no disponible: %s" % exc)

    yield

    async with AsyncSessionLocal() as db:
        await _borrar_usuario_de_prueba(db)
        await db.commit()

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


async def _tirar(user_id: int, monto: str = "5.00", riesgo: str = "medium", filas: int = 12):
    async with AsyncSessionLocal() as db:
        respuesta = await play_plinko_service(
            db,
            user_id,
            PlinkoBetCreate(bet_amount=Decimal(monto), risk=riesgo, rows=filas),
        )
        return respuesta.result_data


# ------------------------------ la semilla ------------------------------

async def test_la_primera_jugada_crea_la_semilla():
    user_id = await _usuario_con_saldo("100.00")

    async with AsyncSessionLocal() as db:
        semilla = await obtener_semilla_activa(db, user_id)

    assert semilla.game_id == GAME_ID
    assert semilla.nonce == 0
    assert semilla.revealed_at is None
    assert hashear_seed(semilla.server_seed) == semilla.server_seed_hash


async def test_lo_publicado_no_incluye_el_server_seed():
    """Si viajara el seed, el jugador calcularía el resultado antes de tirar."""
    user_id = await _usuario_con_saldo("100.00")

    async with AsyncSessionLocal() as db:
        semilla = await obtener_semilla_activa(db, user_id)
        publicado = describir_semilla(semilla)

    assert set(publicado) == {"server_seed_hash", "client_seed", "nonce"}
    assert semilla.server_seed not in publicado.values()


async def test_la_semilla_se_reusa_entre_jugadas():
    user_id = await _usuario_con_saldo("100.00")

    async with AsyncSessionLocal() as db:
        primera = await obtener_semilla_activa(db, user_id)
    async with AsyncSessionLocal() as db:
        segunda = await obtener_semilla_activa(db, user_id)

    assert primera.id == segunda.id


async def test_el_nonce_avanza_una_vez_por_bola():
    user_id = await _usuario_con_saldo("100.00")

    nonces = [(await _tirar(user_id))["nonce"] for _ in range(3)]

    assert nonces == [1, 2, 3]


async def test_dos_bolas_simultaneas_no_comparten_nonce():
    """Mismo nonce sería el mismo camino, y rompería la verificación."""
    user_id = await _usuario_con_saldo("100.00")

    jugadas = await asyncio.gather(*[_tirar(user_id, "1.00") for _ in range(8)])
    nonces = [jugada["nonce"] for jugada in jugadas]

    assert sorted(nonces) == [1, 2, 3, 4, 5, 6, 7, 8]


# ------------------------------ rotación ------------------------------

async def test_rotar_revela_la_semilla_y_deja_otra_activa():
    user_id = await _usuario_con_saldo("100.00")
    await _tirar(user_id)

    async with AsyncSessionLocal() as db:
        semilla_vieja = await obtener_semilla_activa(db, user_id)
        hash_publicado = semilla_vieja.server_seed_hash

    async with AsyncSessionLocal() as db:
        resultado = await rotar_semilla(db, user_id, "mi-semilla")

    assert hashear_seed(resultado["revelada"]["server_seed"]) == hash_publicado
    assert resultado["revelada"]["jugadas"] == 1
    assert resultado["activa"]["client_seed"] == "mi-semilla"
    assert resultado["activa"]["nonce"] == 0


async def test_queda_una_sola_semilla_activa():
    user_id = await _usuario_con_saldo("100.00")
    await _tirar(user_id)

    async with AsyncSessionLocal() as db:
        await rotar_semilla(db, user_id)
        await rotar_semilla(db, user_id)

    async with AsyncSessionLocal() as db:
        activas = await db.scalars(
            select(GameSeed).where(
                GameSeed.user_id == user_id, GameSeed.revealed_at.is_(None)
            )
        )
        reveladas = await db.scalars(
            select(GameSeed).where(
                GameSeed.user_id == user_id, GameSeed.revealed_at.is_not(None)
            )
        )

    assert len(list(activas)) == 1
    assert len(list(reveladas)) == 2


async def test_la_jugada_se_puede_verificar_con_el_seed_revelado():
    """El recorrido completo: tirar, rotar, rehacer la cuenta."""
    user_id = await _usuario_con_saldo("100.00")

    jugadas = [await _tirar(user_id, "1.00", filas=12) for _ in range(3)]

    async with AsyncSessionLocal() as db:
        revelada = (await rotar_semilla(db, user_id))["revelada"]

    for jugada in jugadas:
        camino = derivar_camino(
            revelada["server_seed"], revelada["client_seed"], jugada["nonce"], jugada["rows"]
        )
        assert camino == jugada["path"]
        assert camino.count("R") == jugada["slot_index"]


# ------------------------------ el saldo ------------------------------

async def test_la_bola_descuenta_y_paga():
    user_id = await _usuario_con_saldo("100.00")

    jugada = await _tirar(user_id, "10.00")
    multiplicador = Decimal(jugada["multiplier"])

    esperado = Decimal("90.00") + (Decimal("10.00") * multiplicador).quantize(Decimal("0.01"))
    assert await _saldo(user_id) == esperado


async def test_sin_saldo_no_se_tira():
    user_id = await _usuario_con_saldo("1.00")

    with pytest.raises(Exception) as error:
        await _tirar(user_id, "5.00")

    assert "Saldo insuficiente" in str(error.value)
    assert await _saldo(user_id) == Decimal("1.00")


async def test_ninguna_bola_simultanea_entra_sin_fondos():
    """El débito atómico: con saldo para ninguna, no entra ninguna.

    Sin pagos de por medio el saldo no se recarga, así que las cinco se tienen
    que rechazar.
    """
    user_id = await _usuario_con_saldo("1.00")

    resultados = await asyncio.gather(
        *[_tirar(user_id, "5.00") for _ in range(5)], return_exceptions=True
    )

    assert all(isinstance(resultado, Exception) for resultado in resultados)
    assert await _saldo(user_id) == Decimal("1.00")


async def test_el_saldo_cierra_con_bolas_simultaneas():
    """Plinko paga en el acto, así que el saldo se recarga entre bolas.

    Lo que se verifica entonces no es cuántas entran, sino que la cuenta cierre
    y que el saldo no quede negativo.
    """
    user_id = await _usuario_con_saldo("30.00")
    monto = Decimal("10.00")

    resultados = await asyncio.gather(
        *[_tirar(user_id, "10.00") for _ in range(10)], return_exceptions=True
    )
    aceptadas = [r for r in resultados if not isinstance(r, Exception)]

    pagado = sum(
        (monto * Decimal(jugada["multiplier"])).quantize(Decimal("0.01"))
        for jugada in aceptadas
    )
    esperado = Decimal("30.00") - monto * len(aceptadas) + pagado

    assert aceptadas
    assert await _saldo(user_id) == esperado
    assert await _saldo(user_id) >= 0
