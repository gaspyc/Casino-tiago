"""Mesas de truco entre dos jugadores.

Necesitan Postgres, así que corren dentro del contenedor.
"""

from decimal import Decimal

import pytest

try:
    from fastapi import HTTPException
    from sqlalchemy import delete, select, text

    from app.modules.games.infrastructure.models import TrucoMesa
    from app.modules.games.truco import mesas
    from app.modules.games.truco.mano import jugador_en_turno
    from app.modules.users.infrastructure.models import User
    from app.shared.database import AsyncSessionLocal, engine
except Exception as exc:  # pragma: no cover - entorno sin dependencias
    pytest.skip(
        "Requiere sqlalchemy y Postgres, correr dentro de Docker (%s)" % exc,
        allow_module_level=True,
    )

ANA = "test_mesa_ana"
BETO = "test_mesa_beto"


async def _limpiar(db):
    nombres = (ANA, BETO)
    await db.execute(
        text(
            "DELETE FROM truco_mesas WHERE jugador_0_id IN "
            "(SELECT id FROM users WHERE username = ANY(:nombres)) "
            "OR jugador_1_id IN (SELECT id FROM users WHERE username = ANY(:nombres))"
        ),
        {"nombres": list(nombres)},
    )
    for tabla in ("transactions", "bets", "truco_partidas", "game_seeds"):
        await db.execute(
            text(
                "DELETE FROM %s WHERE user_id IN "
                "(SELECT id FROM users WHERE username = ANY(:nombres))" % tabla
            ),
            {"nombres": list(nombres)},
        )
    await db.execute(delete(User).where(User.username.in_(nombres)))


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


async def _jugadores(saldo: str = "300.00"):
    async with AsyncSessionLocal() as db:
        await _limpiar(db)
        creados = []
        for nombre in (ANA, BETO):
            user = User(
                username=nombre,
                email=nombre + "@example.test",
                hashed_password="x",
                balance=Decimal(saldo),
            )
            db.add(user)
            creados.append(user)
        await db.commit()
        return creados[0].id, creados[1].id


async def _saldo(user_id: int) -> Decimal:
    async with AsyncSessionLocal() as db:
        return await db.scalar(select(User.balance).where(User.id == user_id))


async def _mesa_en_juego(apuesta="50.00"):
    ana, beto = await _jugadores()

    async with AsyncSessionLocal() as db:
        mesa = await mesas.crear_mesa(db, ana, Decimal(apuesta))

    async with AsyncSessionLocal() as db:
        await mesas.sentarse(db, beto, mesa["mesa_id"])

    return ana, beto, mesa["mesa_id"]


# ------------------------------ crear y sentarse ------------------------------

async def test_crear_deja_la_apuesta_puesta_esperando_rival():
    ana, _ = await _jugadores()

    async with AsyncSessionLocal() as db:
        mesa = await mesas.crear_mesa(db, ana, Decimal("50.00"))

    assert mesa["estado"] == "esperando"
    assert mesa["mano"] is None
    assert await _saldo(ana) == Decimal("250.00")


async def test_no_se_puede_estar_en_dos_mesas():
    ana, _ = await _jugadores()

    async with AsyncSessionLocal() as db:
        await mesas.crear_mesa(db, ana, Decimal("50.00"))

        with pytest.raises(HTTPException):
            await mesas.crear_mesa(db, ana, Decimal("50.00"))

    assert await _saldo(ana) == Decimal("250.00")


async def test_sentarse_cobra_y_arranca_la_partida():
    ana, beto, mesa_id = await _mesa_en_juego()

    async with AsyncSessionLocal() as db:
        vista = await mesas.ver_mesa(db, beto, mesa_id)

    assert vista["estado"] == "jugando"
    assert vista["asiento"] == 1
    assert len(vista["mano"]["cartas"]) == 3
    assert await _saldo(ana) == Decimal("250.00")
    assert await _saldo(beto) == Decimal("250.00")


async def test_no_se_puede_sentar_en_la_mesa_propia():
    ana, _ = await _jugadores()

    async with AsyncSessionLocal() as db:
        mesa = await mesas.crear_mesa(db, ana, Decimal("50.00"))

        with pytest.raises(HTTPException):
            await mesas.sentarse(db, ana, mesa["mesa_id"])


async def test_no_se_puede_sentar_en_una_mesa_llena():
    ana, beto, mesa_id = await _mesa_en_juego()

    async with AsyncSessionLocal() as db:
        tercero = User(
            username=ANA + "_x", email=ANA + "x@t.test", hashed_password="x",
            balance=Decimal("300.00"),
        )
        db.add(tercero)
        await db.commit()

        with pytest.raises(HTTPException):
            await mesas.sentarse(db, tercero.id, mesa_id)

        await db.delete(tercero)
        await db.commit()


async def test_sin_saldo_no_se_crea_mesa():
    async with AsyncSessionLocal() as db:
        await _limpiar(db)
        pobre = User(username=ANA, email=ANA + "@t.test", hashed_password="x", balance=Decimal("5.00"))
        db.add(pobre)
        await db.commit()
        pobre_id = pobre.id

    async with AsyncSessionLocal() as db:
        with pytest.raises(HTTPException):
            await mesas.crear_mesa(db, pobre_id, Decimal("50.00"))

    assert await _saldo(pobre_id) == Decimal("5.00")


async def test_el_listado_marca_donde_me_puedo_sentar():
    ana, beto = await _jugadores()

    async with AsyncSessionLocal() as db:
        await mesas.crear_mesa(db, ana, Decimal("50.00"))

    async with AsyncSessionLocal() as db:
        vistas_por_beto = await mesas.listar_mesas(db, beto)
        vistas_por_ana = await mesas.listar_mesas(db, ana)

    assert any(m["puedo_sentarme"] for m in vistas_por_beto)
    assert not any(m["puedo_sentarme"] for m in vistas_por_ana)
    assert any(m["soy_parte"] for m in vistas_por_ana)


# ------------------------------ jugar ------------------------------

async def test_solo_juega_el_que_tiene_el_turno():
    ana, beto, mesa_id = await _mesa_en_juego()

    async with AsyncSessionLocal() as db:
        vista = await mesas.ver_mesa(db, ana, mesa_id)
        de_turno = ana if vista["me_toca"] else beto
        fuera_de_turno = beto if de_turno == ana else ana

        with pytest.raises(HTTPException):
            await mesas.jugar(db, fuera_de_turno, mesa_id, "truco")


async def test_el_que_no_esta_sentado_no_ve_la_mesa():
    ana, beto, mesa_id = await _mesa_en_juego()

    async with AsyncSessionLocal() as db:
        ajeno = User(
            username=BETO + "_x", email=BETO + "x@t.test", hashed_password="x",
            balance=Decimal("10.00"),
        )
        db.add(ajeno)
        await db.commit()

        with pytest.raises(HTTPException) as error:
            await mesas.ver_mesa(db, ajeno.id, mesa_id)

        assert error.value.status_code == 403

        await db.delete(ajeno)
        await db.commit()


async def test_cada_uno_ve_solo_sus_cartas():
    ana, beto, mesa_id = await _mesa_en_juego()

    async with AsyncSessionLocal() as db:
        de_ana = await mesas.ver_mesa(db, ana, mesa_id)
        de_beto = await mesas.ver_mesa(db, beto, mesa_id)

    assert de_ana["mano"]["cartas"] != de_beto["mano"]["cartas"]
    assert de_ana["mano"]["cartas_del_rival"] == 3
    assert not set(de_ana["mano"]["cartas"]) & set(de_beto["mano"]["cartas"])


async def test_la_accion_queda_registrada_y_cambia_el_turno():
    ana, beto, mesa_id = await _mesa_en_juego()

    async with AsyncSessionLocal() as db:
        vista = await mesas.ver_mesa(db, ana, mesa_id)
        de_turno = ana if vista["me_toca"] else beto
        acciones = (await mesas.ver_mesa(db, de_turno, mesa_id))["mano"]["acciones"]
        carta = next(a for a in acciones if a.startswith("jugar:"))

        despues = await mesas.jugar(db, de_turno, mesa_id, carta)

    assert despues["acciones_jugadas"] == 1
    assert despues["me_toca"] is False


# ------------------------------ la plata ------------------------------

async def test_el_ganador_se_lleva_el_pozo_menos_la_comision():
    ana, beto, mesa_id = await _mesa_en_juego()

    async with AsyncSessionLocal() as db:
        fila = await db.get(TrucoMesa, mesa_id)
        await mesas._liquidar(db, fila, 1, mesas.reconstruir(fila))
        await db.commit()

    # pozo 100, comisión 5%, premio 95
    assert await _saldo(ana) == Decimal("250.00")
    assert await _saldo(beto) == Decimal("345.00")


async def test_abandonar_antes_de_que_llegue_nadie_devuelve_la_apuesta():
    ana, _ = await _jugadores()

    async with AsyncSessionLocal() as db:
        mesa = await mesas.crear_mesa(db, ana, Decimal("50.00"))

    async with AsyncSessionLocal() as db:
        vista = await mesas.abandonar(db, ana, mesa["mesa_id"])

    assert vista["estado"] == "terminada"
    assert await _saldo(ana) == Decimal("300.00")


async def test_abandonar_en_juego_es_entregar_la_mesa():
    ana, beto, mesa_id = await _mesa_en_juego()

    async with AsyncSessionLocal() as db:
        vista = await mesas.abandonar(db, ana, mesa_id)

    assert vista["ganador"] == 1
    assert await _saldo(beto) == Decimal("345.00")
    assert await _saldo(ana) == Decimal("250.00")


async def test_una_mesa_terminada_no_se_juega_mas():
    ana, beto, mesa_id = await _mesa_en_juego()

    async with AsyncSessionLocal() as db:
        await mesas.abandonar(db, ana, mesa_id)

    async with AsyncSessionLocal() as db:
        with pytest.raises(HTTPException):
            await mesas.jugar(db, beto, mesa_id, "truco")

        with pytest.raises(HTTPException):
            await mesas.abandonar(db, beto, mesa_id)


async def test_la_casa_se_queda_con_la_comision():
    """Lo que entra menos lo que sale es la comisión, nada se pierde."""
    ana, beto, mesa_id = await _mesa_en_juego()

    async with AsyncSessionLocal() as db:
        fila = await db.get(TrucoMesa, mesa_id)
        await mesas._liquidar(db, fila, 0, mesas.reconstruir(fila))
        await db.commit()
        await db.refresh(fila)

    apostado = Decimal("100.00")
    pagado = Decimal(fila.premio)

    assert Decimal(fila.comision) == Decimal("5.00")
    assert apostado - pagado == Decimal(fila.comision)
    assert await _saldo(ana) + await _saldo(beto) == Decimal("600.00") - Decimal(fila.comision)


# ------------------------------ provably fair ------------------------------

async def test_el_seed_se_revela_recien_al_terminar():
    ana, beto, mesa_id = await _mesa_en_juego()

    async with AsyncSessionLocal() as db:
        jugando = await mesas.ver_mesa(db, ana, mesa_id)

    assert jugando["server_seed"] is None
    assert len(jugando["server_seed_hash"]) == 64

    async with AsyncSessionLocal() as db:
        terminada = await mesas.abandonar(db, ana, mesa_id)

    assert terminada["server_seed"] is not None
