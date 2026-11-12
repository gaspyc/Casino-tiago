"""La mesa de truco contra la casa: plata, turnos y reconstrucción.

Necesitan Postgres, así que corren dentro del contenedor.
"""

from decimal import Decimal

import pytest

try:
    from fastapi import HTTPException
    from sqlalchemy import delete, select, text

    from app.modules.games.infrastructure.models import TrucoPartida
    from app.modules.games.truco import service
    from app.modules.games.truco.mano import jugador_en_turno
    from app.modules.users.infrastructure.models import User
    from app.shared.database import AsyncSessionLocal, engine
except Exception as exc:  # pragma: no cover - entorno sin dependencias
    pytest.skip(
        "Requiere sqlalchemy y Postgres, correr dentro de Docker (%s)" % exc,
        allow_module_level=True,
    )

USERNAME = "test_truco_service"
EMAIL = "test_truco_service@example.test"


async def _limpiar(db):
    for tabla in ("transactions", "bets", "truco_partidas", "game_seeds"):
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


async def _usuario(saldo: str = "500.00") -> int:
    async with AsyncSessionLocal() as db:
        await _limpiar(db)
        user = User(
            username=USERNAME, email=EMAIL, hashed_password="x", balance=Decimal(saldo)
        )
        db.add(user)
        await db.commit()
        return user.id


async def _saldo(user_id: int) -> Decimal:
    async with AsyncSessionLocal() as db:
        return await db.scalar(select(User.balance).where(User.id == user_id))


async def _empezar(user_id: int, monto="50.00"):
    async with AsyncSessionLocal() as db:
        return await service.empezar_partida(db, user_id, Decimal(monto))


async def _jugar_hasta_el_final(user_id: int, estado: dict, limite: int = 400) -> dict:
    """Juega como un jugador bobo: primera carta que pueda, y quiere todo."""
    jugadas = 0
    while not estado["terminada"]:
        jugadas += 1
        assert jugadas < limite, "la partida no termina"

        acciones = estado["mano"]["acciones"]
        assert acciones, "el jugador se quedó sin acciones y no es su turno"

        carta = next((a for a in acciones if a.startswith("jugar:")), None)
        accion = carta or ("quiero" if "quiero" in acciones else acciones[0])

        async with AsyncSessionLocal() as db:
            estado = await service.jugar_accion(db, user_id, accion)

    return estado


# ------------------------------ empezar ------------------------------

async def test_empezar_cobra_la_apuesta_y_reparte():
    user_id = await _usuario("500.00")

    estado = await _empezar(user_id, "50.00")

    assert await _saldo(user_id) == Decimal("450.00")
    assert len(estado["mano"]["cartas"]) == 3
    assert estado["mano"]["cartas_del_rival"] == 3
    assert estado["puntos"] == [0, 0]


async def test_sin_saldo_no_hay_partida():
    user_id = await _usuario("10.00")

    with pytest.raises(HTTPException) as error:
        await _empezar(user_id, "50.00")

    assert error.value.status_code == 400
    assert await _saldo(user_id) == Decimal("10.00")


async def test_no_se_pueden_tener_dos_partidas_abiertas():
    user_id = await _usuario("500.00")
    await _empezar(user_id)

    with pytest.raises(HTTPException):
        await _empezar(user_id)

    assert await _saldo(user_id) == Decimal("450.00")  # cobró una sola


@pytest.mark.parametrize("monto", ["0.00", "-50.00", "100000.00"])
async def test_montos_invalidos(monto):
    user_id = await _usuario("500.00")

    with pytest.raises(HTTPException):
        await _empezar(user_id, monto)

    assert await _saldo(user_id) == Decimal("500.00")


async def test_el_hash_se_publica_y_el_seed_no():
    user_id = await _usuario()

    estado = await _empezar(user_id)

    assert len(estado["server_seed_hash"]) == 64
    assert estado["server_seed"] is None


# ------------------------------ jugar ------------------------------

async def test_no_se_puede_jugar_una_accion_que_no_toca():
    user_id = await _usuario()
    await _empezar(user_id)

    async with AsyncSessionLocal() as db:
        with pytest.raises(HTTPException) as error:
            await service.jugar_accion(db, user_id, "jugar:1E")

    assert error.value.status_code == 400


async def test_no_se_puede_jugar_sin_partida():
    user_id = await _usuario()

    async with AsyncSessionLocal() as db:
        with pytest.raises(HTTPException) as error:
            await service.jugar_accion(db, user_id, "truco")

    assert error.value.status_code == 404


async def test_cada_accion_queda_registrada():
    user_id = await _usuario()
    estado = await _empezar(user_id)
    antes = estado["acciones_jugadas"]

    async with AsyncSessionLocal() as db:
        estado = await service.jugar_accion(db, user_id, estado["mano"]["acciones"][0])

    assert estado["acciones_jugadas"] > antes


async def test_la_partida_se_reconstruye_igual_desde_las_acciones():
    """El estado no se guarda: se rehace reproduciendo las acciones."""
    user_id = await _usuario()
    estado = await _empezar(user_id)

    async with AsyncSessionLocal() as db:
        estado = await service.jugar_accion(db, user_id, estado["mano"]["acciones"][0])

    async with AsyncSessionLocal() as db:
        fila = await service.partida_abierta(db, user_id)
        rehecha = service.reconstruir(fila)

    assert rehecha.estado(para=0)["mano"]["cartas"] == estado["mano"]["cartas"]
    assert rehecha.puntos == estado["puntos"]


async def test_despues_de_jugar_le_toca_siempre_al_jugador():
    """El servicio adelanta a la casa hasta que vuelve a ser tu turno."""
    user_id = await _usuario()
    estado = await _empezar(user_id)

    for _ in range(5):
        if estado["terminada"]:
            break

        async with AsyncSessionLocal() as db:
            fila = await service.partida_abierta(db, user_id)
            partida = service.reconstruir(fila)
            assert jugador_en_turno(partida.mano_actual) == service.JUGADOR

            estado = await service.jugar_accion(
                db, user_id, estado["mano"]["acciones"][0]
            )


# ------------------------------ la plata ------------------------------

async def test_una_partida_entera_cierra_la_cuenta():
    user_id = await _usuario("500.00")
    estado = await _empezar(user_id, "50.00")

    estado = await _jugar_hasta_el_final(user_id, estado)

    esperado = Decimal("450.00") + Decimal(estado["payout"])
    assert await _saldo(user_id) == esperado
    assert estado["ganador"] in (0, 1)
    assert max(estado["puntos"]) >= 30


async def test_al_terminar_se_revela_el_seed_y_se_libera_la_mesa():
    user_id = await _usuario("500.00")
    estado = await _empezar(user_id, "50.00")

    estado = await _jugar_hasta_el_final(user_id, estado)

    assert estado["server_seed"] is not None

    async with AsyncSessionLocal() as db:
        assert await service.partida_abierta(db, user_id) is None


async def test_el_pago_es_la_apuesta_por_el_multiplicador():
    user_id = await _usuario("500.00")

    async with AsyncSessionLocal() as db:
        fila = TrucoPartida(
            user_id=user_id,
            apuesta=Decimal("50.00"),
            server_seed="s",
            server_seed_hash="h",
            client_seed="c",
            nonce_base=0,
            acciones=[],
        )
        db.add(fila)
        await db.commit()

        class _PartidaGanada:
            terminada = True
            ganador = service.JUGADOR
            puntos = [30, 12]
            manos_jugadas = 9

        await service._liquidar(db, fila, _PartidaGanada())
        await db.commit()

    assert fila.payout == Decimal("95.00")  # 50 * 1.90
    assert await _saldo(user_id) == Decimal("595.00")


async def test_si_gana_la_casa_no_paga_nada():
    user_id = await _usuario("500.00")

    async with AsyncSessionLocal() as db:
        fila = TrucoPartida(
            user_id=user_id,
            apuesta=Decimal("50.00"),
            server_seed="s",
            server_seed_hash="h",
            client_seed="c",
            nonce_base=0,
            acciones=[],
        )
        db.add(fila)
        await db.commit()

        class _PartidaPerdida:
            terminada = True
            ganador = service.CASA
            puntos = [11, 30]
            manos_jugadas = 9

        await service._liquidar(db, fila, _PartidaPerdida())
        await db.commit()

    assert fila.payout == Decimal("0.00")
    assert await _saldo(user_id) == Decimal("500.00")
