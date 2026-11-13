"""El mines contra la base: la plata, la grilla abierta y el compromiso.

Necesitan Postgres, así que corren dentro del contenedor.
"""

import hashlib
from decimal import Decimal

import pytest

try:
    from fastapi import HTTPException
    from sqlalchemy import delete, select, text

    from app.modules.games.infrastructure.models import GameSeed, MinesGame
    from app.modules.games.mines.fairness import posiciones_de_minas
    from app.modules.games.mines.paytable import CASILLAS, premio
    from app.modules.games.mines.service import (
        GAME_ID,
        cobrar,
        destapar,
        empezar,
        obtener_semilla_mines,
        rotar_semilla_mines,
        ver_activa,
    )
    from app.modules.users.infrastructure.models import User
    from app.shared.database import AsyncSessionLocal, engine
except Exception as exc:  # pragma: no cover - entorno sin dependencias
    pytest.skip(
        "Requiere sqlalchemy y Postgres, correr dentro de Docker (%s)" % exc,
        allow_module_level=True,
    )

USERNAME = "test_mines"
EMAIL = "test_mines@example.test"
SALDO = Decimal("500.00")
APUESTA = Decimal("10.00")


async def _limpiar(db):
    # mines_games antes que game_seeds: tiene una FK a la semilla.
    for tabla in ("transactions", "bets", "mines_games", "game_seeds"):
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


async def _minas_de_la_grilla(user_id: int) -> set:
    """Las minas de la grilla abierta, mirando el seed como no puede el jugador."""
    async with AsyncSessionLocal() as db:
        fila = await db.scalar(
            select(MinesGame).where(
                MinesGame.user_id == user_id, MinesGame.status == "ACTIVE"
            )
        )
        semilla = await db.get(GameSeed, fila.seed_id)
        return posiciones_de_minas(
            semilla.server_seed, fila.client_seed, fila.nonce, fila.minas
        )


async def _empezar(user_id: int, minas: int = 3, apuesta: Decimal = APUESTA):
    async with AsyncSessionLocal() as db:
        return await empezar(db, user_id, apuesta, minas)


async def _destapar(user_id: int, casilla: int):
    async with AsyncSessionLocal() as db:
        return await destapar(db, user_id, casilla)


# ------------------------------ empezar ------------------------------

async def test_empezar_cobra_la_apuesta_y_deja_la_grilla_vacia():
    user_id = await _jugador()
    estado = await _empezar(user_id)

    assert estado.status == "ACTIVE"
    assert estado.destapadas == []
    assert estado.multiplicador == Decimal("1.00")
    assert estado.payout == Decimal("0.00")
    assert await _saldo(user_id) == SALDO - APUESTA


async def test_sin_saldo_no_se_empieza():
    user_id = await _jugador()

    async with AsyncSessionLocal() as db:
        with pytest.raises(HTTPException) as error:
            await empezar(db, user_id, Decimal("9999.00"), 3)

        assert error.value.status_code == 400

    assert await _saldo(user_id) == SALDO


async def test_no_se_pueden_tener_dos_grillas_abiertas():
    """Dos grillas abiertas serían dos apuestas debitadas y una sola pantalla."""
    user_id = await _jugador()
    await _empezar(user_id)

    async with AsyncSessionLocal() as db:
        with pytest.raises(HTTPException) as error:
            await empezar(db, user_id, APUESTA, 3)

        assert error.value.status_code == 409

    # Y la segunda apuesta no se cobró.
    assert await _saldo(user_id) == SALDO - APUESTA


# ------------------------------ destapar ------------------------------

async def test_destapar_limpio_sube_el_multiplicador_sin_pagar_todavia():
    user_id = await _jugador()
    await _empezar(user_id, minas=3)
    minas = await _minas_de_la_grilla(user_id)

    limpia = next(casilla for casilla in range(CASILLAS) if casilla not in minas)
    estado = await _destapar(user_id, limpia)

    assert estado.status == "ACTIVE"
    assert estado.destapadas == [limpia]
    assert estado.multiplicador > Decimal("1.00")
    assert estado.payout == Decimal("0.00")
    # La plata no se movió: sigue debitada la apuesta y nada más.
    assert await _saldo(user_id) == SALDO - APUESTA


async def test_tocar_una_mina_pierde_la_apuesta_y_muestra_el_tablero():
    user_id = await _jugador()
    await _empezar(user_id, minas=5)
    minas = await _minas_de_la_grilla(user_id)

    estado = await _destapar(user_id, sorted(minas)[0])

    assert estado.status == "BUSTED"
    assert estado.payout == Decimal("0.00")
    assert estado.net_profit == -APUESTA
    # Recién ahora se ve dónde estaban todas.
    assert estado.minas_en == sorted(minas)
    assert await _saldo(user_id) == SALDO - APUESTA


async def test_no_se_destapa_dos_veces_la_misma_casilla():
    user_id = await _jugador()
    await _empezar(user_id)
    minas = await _minas_de_la_grilla(user_id)

    limpia = next(casilla for casilla in range(CASILLAS) if casilla not in minas)
    await _destapar(user_id, limpia)

    async with AsyncSessionLocal() as db:
        with pytest.raises(HTTPException) as error:
            await destapar(db, user_id, limpia)

        assert error.value.status_code == 400


async def test_sin_grilla_abierta_no_se_destapa():
    user_id = await _jugador()

    async with AsyncSessionLocal() as db:
        with pytest.raises(HTTPException) as error:
            await destapar(db, user_id, 0)

        assert error.value.status_code == 404


async def test_limpiar_el_tablero_cobra_solo():
    """Con 24 minas hay una sola casilla limpia: destaparla termina la grilla."""
    user_id = await _jugador()
    await _empezar(user_id, minas=24)
    minas = await _minas_de_la_grilla(user_id)

    unica = next(casilla for casilla in range(CASILLAS) if casilla not in minas)
    estado = await _destapar(user_id, unica)

    assert estado.status == "CASHED"
    assert estado.payout == premio(APUESTA, 24, 1)
    assert estado.payout == Decimal("240.00")  # 24x, la apuesta era 10
    assert await _saldo(user_id) == SALDO - APUESTA + estado.payout


# ------------------------------ cobrar ------------------------------

async def test_cobrar_paga_lo_que_dice_la_tabla():
    user_id = await _jugador()
    await _empezar(user_id, minas=3)
    minas = await _minas_de_la_grilla(user_id)

    limpias = [casilla for casilla in range(CASILLAS) if casilla not in minas][:4]
    for casilla in limpias:
        await _destapar(user_id, casilla)

    async with AsyncSessionLocal() as db:
        estado = await cobrar(db, user_id)

    assert estado.status == "CASHED"
    assert estado.payout == premio(APUESTA, 3, 4)
    assert await _saldo(user_id) == SALDO - APUESTA + estado.payout


async def test_no_se_cobra_sin_destapar_nada():
    """Cobrar en seco devolvería la apuesta: mover saldo sin arriesgar."""
    user_id = await _jugador()
    await _empezar(user_id)

    async with AsyncSessionLocal() as db:
        with pytest.raises(HTTPException) as error:
            await cobrar(db, user_id)

        assert error.value.status_code == 400

    assert await _saldo(user_id) == SALDO - APUESTA


async def test_una_grilla_cerrada_no_se_juega_mas():
    user_id = await _jugador()
    await _empezar(user_id, minas=5)
    minas = await _minas_de_la_grilla(user_id)

    await _destapar(user_id, sorted(minas)[0])  # explota

    async with AsyncSessionLocal() as db:
        with pytest.raises(HTTPException):
            await destapar(db, user_id, 0)

        with pytest.raises(HTTPException):
            await cobrar(db, user_id)


async def test_la_plata_que_sale_es_la_que_dice_la_grilla():
    """Lo que entra menos lo que sale tiene que cerrar, grilla por grilla."""
    user_id = await _jugador()
    saldo = SALDO

    for _ in range(8):
        await _empezar(user_id, minas=4)
        minas = await _minas_de_la_grilla(user_id)
        limpias = [c for c in range(CASILLAS) if c not in minas][:3]

        for casilla in limpias:
            await _destapar(user_id, casilla)

        async with AsyncSessionLocal() as db:
            estado = await cobrar(db, user_id)

        saldo = saldo - APUESTA + estado.payout
        assert await _saldo(user_id) == saldo


# ------------------------------ retomar ------------------------------

async def test_la_grilla_sin_terminar_se_puede_retomar():
    user_id = await _jugador()
    empezada = await _empezar(user_id)
    minas = await _minas_de_la_grilla(user_id)
    limpia = next(casilla for casilla in range(CASILLAS) if casilla not in minas)
    await _destapar(user_id, limpia)

    async with AsyncSessionLocal() as db:
        retomada = await ver_activa(db, user_id)

    assert retomada is not None
    assert retomada.game_id == empezada.game_id
    assert retomada.destapadas == [limpia]
    # Y sin soplar dónde están las minas.
    assert retomada.minas_en is None


async def test_sin_grilla_abierta_no_hay_nada_que_retomar():
    user_id = await _jugador()

    async with AsyncSessionLocal() as db:
        assert await ver_activa(db, user_id) is None


# ------------------------------ provably fair ------------------------------

async def test_la_grilla_viene_con_el_hash_pero_no_con_el_seed():
    user_id = await _jugador()

    async with AsyncSessionLocal() as db:
        semilla = await obtener_semilla_mines(db, user_id)
        server_seed = semilla.server_seed
        hash_publicado = semilla.server_seed_hash

    estado = await _empezar(user_id)

    assert estado.server_seed_hash == hash_publicado
    assert len(estado.server_seed_hash) == 64
    assert server_seed not in estado.model_dump_json()


async def test_al_revelar_el_seed_la_mina_estaba_donde_decia():
    """La verificación que le importa al jugador: la mina ya estaba ahí."""
    user_id = await _jugador()
    estado = await _empezar(user_id, minas=5)
    minas = await _minas_de_la_grilla(user_id)

    explotada = await _destapar(user_id, sorted(minas)[0])

    async with AsyncSessionLocal() as db:
        rotada = await rotar_semilla_mines(db, user_id)

    revelada = rotada["revelada"]
    assert (
        hashlib.sha256(revelada["server_seed"].encode()).hexdigest()
        == estado.server_seed_hash
    )

    rehecho = posiciones_de_minas(
        revelada["server_seed"], revelada["client_seed"], estado.nonce, 5
    )
    assert sorted(rehecho) == explotada.minas_en


async def test_no_se_puede_revelar_el_seed_con_una_grilla_abierta():
    """El server seed es el mapa de las minas."""
    user_id = await _jugador()
    await _empezar(user_id)

    async with AsyncSessionLocal() as db:
        with pytest.raises(HTTPException) as error:
            await rotar_semilla_mines(db, user_id)

        assert error.value.status_code == 409

    minas = await _minas_de_la_grilla(user_id)
    await _destapar(user_id, sorted(minas)[0])

    async with AsyncSessionLocal() as db:
        rotada = await rotar_semilla_mines(db, user_id)

    assert rotada["revelada"]["server_seed"]


async def test_cada_grilla_consume_un_nonce_distinto():
    user_id = await _jugador()

    nonces = []
    for _ in range(4):
        estado = await _empezar(user_id, minas=24)
        nonces.append(estado.nonce)

        minas = await _minas_de_la_grilla(user_id)
        unica = next(c for c in range(CASILLAS) if c not in minas)
        await _destapar(user_id, unica)

    assert nonces == [1, 2, 3, 4]


async def test_grillas_distintas_esconden_las_minas_en_lugares_distintos():
    """Si el nonce no entrara en la cuenta, todas las grillas serían iguales."""
    user_id = await _jugador()
    tableros = set()

    for _ in range(10):
        await _empezar(user_id, minas=5)
        tableros.add(tuple(sorted(await _minas_de_la_grilla(user_id))))

        minas = await _minas_de_la_grilla(user_id)
        await _destapar(user_id, sorted(minas)[0])

    assert len(tableros) == 10
