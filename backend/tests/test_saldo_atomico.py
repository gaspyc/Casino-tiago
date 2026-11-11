"""Tests del débito atómico contra Postgres.

Necesitan la base levantada, así que corren dentro de Docker:

    docker compose run --rm backend sh -c "pip install -q pytest pytest-asyncio && pytest tests -q"
"""

import asyncio
from decimal import Decimal

import pytest

try:
    from sqlalchemy import delete, select, text
    from sqlalchemy.exc import IntegrityError

    from app.modules.users.infrastructure.models import User
    from app.modules.wallet.application.balance import credit, debit
    from app.shared.database import AsyncSessionLocal, engine
except Exception as exc:  # pragma: no cover - entorno sin sqlalchemy/DB
    pytest.skip(
        "Requiere sqlalchemy y Postgres, correr dentro de Docker (%s)" % exc,
        allow_module_level=True,
    )

USERNAME = "test_concurrencia"
EMAIL = "test_concurrencia@example.test"


async def _borrar_usuario_de_prueba(db):
    """Borra el usuario y todo lo que lo referencia por FK."""
    for tabla in ("transactions", "bets", "crash_bets", "blackjack_games"):
        await db.execute(
            text(
                "DELETE FROM %s WHERE user_id IN "
                "(SELECT id FROM users WHERE username = :username)" % tabla
            ),
            {"username": USERNAME},
        )
    await db.execute(delete(User).where(User.username == USERNAME))


@pytest.fixture(autouse=True)
async def _pool_del_loop_actual():
    """El engine es global y el pool queda atado al loop que lo abrió.

    pytest-asyncio crea un loop por test, así que hay que descartar las
    conexiones viejas antes y después de cada uno.
    """
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
            username=USERNAME,
            email=EMAIL,
            hashed_password="no-importa",
            balance=Decimal(saldo),
        )
        db.add(user)
        await db.commit()
        return user.id


async def _saldo(user_id: int) -> Decimal:
    async with AsyncSessionLocal() as db:
        return await db.scalar(select(User.balance).where(User.id == user_id))


async def _apostar(user_id: int, monto: str) -> bool:
    """Una apuesta completa, con su propia sesión y su propio commit."""
    async with AsyncSessionLocal() as db:
        gano = await debit(db, user_id, Decimal(monto))
        if gano:
            await db.commit()
        return gano


async def _pagar(user_id: int, monto: str) -> None:
    async with AsyncSessionLocal() as db:
        await credit(db, user_id, Decimal(monto))
        await db.commit()


async def test_solo_una_apuesta_concurrente_gana_el_saldo():
    """El caso que rompía: 10 apuestas simultáneas contra saldo para una sola.

    Con el patrón viejo (leer, comparar en Python, restar) las 10 leían saldo
    100, las 10 pasaban la validación y las 10 cobraban.
    """
    user_id = await _usuario_con_saldo("100.00")

    resultados = await asyncio.gather(*[_apostar(user_id, "100.00") for _ in range(10)])

    assert sum(resultados) == 1
    assert await _saldo(user_id) == Decimal("0.00")


async def test_todas_las_apuestas_pasan_si_el_saldo_alcanza():
    user_id = await _usuario_con_saldo("1000.00")

    resultados = await asyncio.gather(*[_apostar(user_id, "100.00") for _ in range(10)])

    assert all(resultados)
    assert await _saldo(user_id) == Decimal("0.00")


async def test_debitos_y_pagos_simultaneos_no_se_pisan():
    """Los pagos también son un UPDATE relativo: no pueden pisar un débito."""
    user_id = await _usuario_con_saldo("100.00")

    tareas = [_apostar(user_id, "10.00") for _ in range(5)]
    tareas += [_pagar(user_id, "10.00") for _ in range(5)]
    await asyncio.gather(*tareas)

    assert await _saldo(user_id) == Decimal("100.00")


async def test_saldo_insuficiente_no_deja_rastro():
    user_id = await _usuario_con_saldo("10.00")

    assert await _apostar(user_id, "10.01") is False
    assert await _saldo(user_id) == Decimal("10.00")


@pytest.mark.parametrize("monto", ["0.00", "-1.00", "-100000.00"])
async def test_debitar_montos_no_positivos_es_un_error(monto):
    user_id = await _usuario_con_saldo("100.00")

    async with AsyncSessionLocal() as db:
        with pytest.raises(ValueError):
            await debit(db, user_id, Decimal(monto))

    assert await _saldo(user_id) == Decimal("100.00")


async def test_la_base_rechaza_saldos_negativos():
    """Red de contención: aunque alguien escriba el UPDATE a mano."""
    user_id = await _usuario_con_saldo("50.00")

    with pytest.raises(IntegrityError):
        async with AsyncSessionLocal() as db:
            await db.execute(
                text("UPDATE users SET balance = balance - 100 WHERE id = :id"),
                {"id": user_id},
            )
            await db.commit()

    assert await _saldo(user_id) == Decimal("50.00")

