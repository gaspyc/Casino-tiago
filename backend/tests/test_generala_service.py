"""La generala contra la casa: la plata, el registro de acciones y el seed.

Necesitan Postgres, así que corren dentro del contenedor.
"""

import hashlib
from decimal import Decimal

import pytest

try:
    from fastapi import HTTPException
    from sqlalchemy import delete, select, text

    from app.modules.games.generala.service import (
        APUESTA_MAXIMA,
        CASA,
        JUGADOR,
        MULTIPLICADOR_DE_PAGO,
        empezar_partida,
        jugar_accion,
        partida_abierta,
        reconstruir,
    )
    from app.modules.games.infrastructure.models import GeneralaPartida
    from app.modules.users.infrastructure.models import User
    from app.shared.database import AsyncSessionLocal, engine
except Exception as exc:  # pragma: no cover - entorno sin dependencias
    pytest.skip(
        "Requiere sqlalchemy y Postgres, correr dentro de Docker (%s)" % exc,
        allow_module_level=True,
    )

USERNAME = "test_generala"
EMAIL = "test_generala@example.test"
SALDO = Decimal("500.00")
APUESTA = Decimal("20.00")


async def _limpiar(db):
    for tabla in ("transactions", "bets", "generala_partidas"):
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
        await _limpiar(db)
        await db.commit()

    await engine.dispose()


async def _jugador() -> int:
    async with AsyncSessionLocal() as db:
        await _limpiar(db)
        user = User(
            username=USERNAME, email=EMAIL, hashed_password="x", balance=SALDO
        )
        db.add(user)
        await db.commit()
        return user.id


async def _saldo(user_id: int) -> Decimal:
    async with AsyncSessionLocal() as db:
        return await db.scalar(select(User.balance).where(User.id == user_id))


async def _empezar(user_id: int, apuesta: Decimal = APUESTA):
    async with AsyncSessionLocal() as db:
        return await empezar_partida(db, user_id, apuesta)


async def _jugar(user_id: int, accion: str):
    async with AsyncSessionLocal() as db:
        return await jugar_accion(db, user_id, accion)


async def _jugar_hasta_el_final(user_id: int, estado):
    """Termina la partida anotando siempre la primera categoría disponible."""
    while not estado["terminada"]:
        turno = estado.get("turno")
        if turno is None:
            break

        anotar = next(a for a in turno["acciones"] if a.startswith("anotar:"))
        estado = await _jugar(user_id, anotar)

    return estado


# ------------------------------ empezar ------------------------------

async def test_empezar_cobra_la_apuesta_y_reparte():
    user_id = await _jugador()
    estado = await _empezar(user_id)

    assert estado["apuesta"] == "20.00"
    assert await _saldo(user_id) == SALDO - APUESTA
    assert len(estado["turno"]["dados"]) == 5
    assert estado["totales"] == [0, 0]


async def test_sin_saldo_no_se_empieza():
    user_id = await _jugador()

    async with AsyncSessionLocal() as db:
        with pytest.raises(HTTPException):
            await empezar_partida(db, user_id, Decimal("9999.00"))

    assert await _saldo(user_id) == SALDO


async def test_la_apuesta_tiene_tope():
    user_id = await _jugador()

    async with AsyncSessionLocal() as db:
        with pytest.raises(HTTPException) as error:
            await empezar_partida(db, user_id, APUESTA_MAXIMA + Decimal("1"))

        assert error.value.status_code == 400

    assert await _saldo(user_id) == SALDO


async def test_no_se_tienen_dos_partidas_abiertas():
    user_id = await _jugador()
    await _empezar(user_id)

    async with AsyncSessionLocal() as db:
        with pytest.raises(HTTPException):
            await empezar_partida(db, user_id, APUESTA)

    assert await _saldo(user_id) == SALDO - APUESTA


async def test_el_que_empieza_se_alterna_entre_partidas():
    """Arrancar vale poco, pero vale: dárselo siempre al mismo sería regalarlo."""
    user_id = await _jugador()
    empiezan = []

    for _ in range(4):
        estado = await _empezar(user_id)
        empiezan.append(estado["empieza"])
        await _jugar_hasta_el_final(user_id, estado)

    assert empiezan == [0, 1, 0, 1]


# ------------------------------ jugar ------------------------------

async def test_la_accion_queda_registrada():
    user_id = await _jugador()
    estado = await _empezar(user_id)

    if estado["terminada"]:
        pytest.skip("Generala servida de la casa en la primera")

    antes = estado["acciones_jugadas"]
    estado = await _jugar(user_id, "tirar:0")

    assert estado["acciones_jugadas"] > antes
    assert estado["turno"]["tirada"] == 2


async def test_una_accion_invalida_no_rompe_ni_avanza():
    user_id = await _jugador()
    estado = await _empezar(user_id)

    if estado["terminada"]:
        pytest.skip("Generala servida de la casa en la primera")

    async with AsyncSessionLocal() as db:
        with pytest.raises(HTTPException) as error:
            await jugar_accion(db, user_id, "anotar:escalera_real")

        assert error.value.status_code == 400

    async with AsyncSessionLocal() as db:
        fila = await partida_abierta(db, user_id)
        assert len(fila.acciones) == estado["acciones_jugadas"]


async def test_sin_partida_abierta_no_se_juega():
    user_id = await _jugador()

    async with AsyncSessionLocal() as db:
        with pytest.raises(HTTPException) as error:
            await jugar_accion(db, user_id, "tirar:0")

        assert error.value.status_code == 404


async def test_no_se_tira_cuatro_veces():
    user_id = await _jugador()
    estado = await _empezar(user_id)

    if estado["terminada"]:
        pytest.skip("Generala servida de la casa en la primera")

    estado = await _jugar(user_id, "tirar:0")
    estado = await _jugar(user_id, "tirar:0")

    assert not estado["turno"]["puede_tirar"]

    async with AsyncSessionLocal() as db:
        with pytest.raises(HTTPException):
            await jugar_accion(db, user_id, "tirar:0")


# ------------------------------ la plata ------------------------------

async def test_la_partida_termina_y_la_plata_cierra():
    user_id = await _jugador()
    estado = await _empezar(user_id)
    estado = await _jugar_hasta_el_final(user_id, estado)

    assert estado["terminada"]
    saldo = await _saldo(user_id)

    if estado["ganador"] == JUGADOR:
        pago = (APUESTA * MULTIPLICADOR_DE_PAGO).quantize(Decimal("0.01"))
        assert saldo == SALDO - APUESTA + pago
    elif estado["ganador"] == CASA:
        assert saldo == SALDO - APUESTA
    else:
        # Empate: vuelve la apuesta.
        assert saldo == SALDO


async def test_el_empate_devuelve_la_apuesta():
    """Quedársela sería cobrarles a los dos por no perder."""
    user_id = await _jugador()
    estado = await _empezar(user_id)

    async with AsyncSessionLocal() as db:
        fila = await partida_abierta(db, user_id)
        partida = reconstruir(fila)

        # Se fuerza el empate sobre la partida reconstruida.
        partida.terminada = True
        partida.ganador = None

        from app.modules.games.generala.service import _liquidar

        await _liquidar(db, fila, partida)
        await db.commit()

    assert await _saldo(user_id) == SALDO


async def test_una_partida_terminada_no_se_juega_mas():
    user_id = await _jugador()
    estado = await _empezar(user_id)
    await _jugar_hasta_el_final(user_id, estado)

    async with AsyncSessionLocal() as db:
        assert await partida_abierta(db, user_id) is None

        with pytest.raises(HTTPException):
            await jugar_accion(db, user_id, "tirar:0")


async def test_varias_partidas_seguidas_cierran_la_caja():
    """Lo que entra menos lo que sale tiene que coincidir, partida por partida."""
    user_id = await _jugador()
    saldo = SALDO

    for _ in range(5):
        estado = await _empezar(user_id)
        estado = await _jugar_hasta_el_final(user_id, estado)

        saldo = saldo - APUESTA + Decimal(estado["payout"])
        assert await _saldo(user_id) == saldo


# ------------------------------ reconstruir y verificar ------------------------------

async def test_la_partida_se_rehace_desde_las_acciones():
    user_id = await _jugador()
    estado = await _empezar(user_id)

    if estado["terminada"]:
        pytest.skip("Generala servida de la casa en la primera")

    await _jugar(user_id, "tirar:0,1")

    async with AsyncSessionLocal() as db:
        fila = await partida_abierta(db, user_id)
        una = reconstruir(fila)
        otra = reconstruir(fila)

    assert una.planillas == otra.planillas
    assert una.turno.dados == otra.turno.dados
    assert una.en_turno == otra.en_turno


async def test_el_seed_se_revela_recien_al_terminar():
    """Con el seed en la mano el jugador sabría qué dados vienen."""
    user_id = await _jugador()
    estado = await _empezar(user_id)

    if not estado["terminada"]:
        assert estado["server_seed"] is None
        assert len(estado["server_seed_hash"]) == 64

        estado = await _jugar_hasta_el_final(user_id, estado)

    assert estado["server_seed"] is not None
    assert (
        hashlib.sha256(estado["server_seed"].encode()).hexdigest()
        == estado["server_seed_hash"]
    )


async def test_con_el_seed_revelado_los_dados_se_rehacen():
    user_id = await _jugador()
    estado = await _empezar(user_id)
    estado = await _jugar_hasta_el_final(user_id, estado)

    async with AsyncSessionLocal() as db:
        fila = await db.scalar(
            select(GeneralaPartida)
            .where(GeneralaPartida.user_id == user_id)
            .order_by(GeneralaPartida.id.desc())
        )

    # Lo mismo que puede hacer cualquiera con lo que se publicó.
    rehecha = reconstruir(fila)

    assert rehecha.terminada
    assert rehecha.ganador == estado["ganador"]
    assert [rehecha.total(0), rehecha.total(1)] == estado["totales"]
