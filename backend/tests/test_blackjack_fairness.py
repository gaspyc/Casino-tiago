"""Provably fair del blackjack: el mazo sale del seed y se puede rehacer.

Necesitan Postgres, así que corren dentro del contenedor.
"""

import hashlib
from collections import Counter
from decimal import Decimal

import pytest

try:
    from fastapi import HTTPException
    from sqlalchemy import delete, select, text

    from app.modules.games.blackjack.fairness import MAZO, mezclar_mazo
    from app.modules.games.blackjack.schemas import BlackjackAction, BlackjackBetCreate
    from app.modules.games.blackjack.service import (
        GAME_ID,
        hit_blackjack_service,
        obtener_mano_activa,
        obtener_semilla_blackjack,
        rotar_semilla_blackjack,
        stand_blackjack_service,
        start_blackjack_service,
    )
    from app.modules.games.infrastructure.models import BlackjackGame, GameSeed
    from app.modules.games.shared.mezcla import flujo_de_bytes, indice_uniforme
    from app.modules.users.infrastructure.models import User
    from app.shared.database import AsyncSessionLocal, engine
except Exception as exc:  # pragma: no cover - entorno sin dependencias
    pytest.skip(
        "Requiere sqlalchemy y Postgres, correr dentro de Docker (%s)" % exc,
        allow_module_level=True,
    )

USERNAME = "test_bj_fairness"
EMAIL = "test_bj_fairness@example.test"


async def _limpiar(db):
    # blackjack_games antes que game_seeds: tiene una FK a la semilla.
    for tabla in ("transactions", "bets", "blackjack_games", "game_seeds"):
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


async def _jugador(saldo: str = "500.00") -> int:
    async with AsyncSessionLocal() as db:
        await _limpiar(db)
        user = User(
            username=USERNAME,
            email=EMAIL,
            hashed_password="x",
            balance=Decimal(saldo),
        )
        db.add(user)
        await db.commit()
        return user.id


async def _mano(user_id: int, apuesta: str = "10.00"):
    async with AsyncSessionLocal() as db:
        return await start_blackjack_service(
            db, user_id, BlackjackBetCreate(bet_amount=Decimal(apuesta))
        )


async def _cerrar(user_id: int, respuesta):
    if respuesta.status != "ACTIVE":
        return

    async with AsyncSessionLocal() as db:
        await stand_blackjack_service(
            db, user_id, BlackjackAction(game_id=respuesta.game_id)
        )


# ------------------------------ la mezcla ------------------------------

def test_el_mazo_mezclado_sigue_siendo_un_mazo():
    for nonce in range(200):
        mazo = mezclar_mazo("seed", "cliente", nonce)
        assert sorted(mazo) == sorted(MAZO)


def test_la_mezcla_es_determinista_y_cambia_con_cada_nonce():
    primera = mezclar_mazo("seed", "cliente", 1)

    assert mezclar_mazo("seed", "cliente", 1) == primera
    assert mezclar_mazo("seed", "cliente", 2) != primera
    assert mezclar_mazo("otro-seed", "cliente", 1) != primera
    assert mezclar_mazo("seed", "otro-cliente", 1) != primera


def test_no_hay_sesgo_del_modulo_en_la_carta_de_arriba():
    """52 no divide a 256: sin muestreo con rechazo algunas cartas saldrían más.

    Con 260.000 mezclas cada carta debería quedar arriba unas 5000 veces. El
    umbral es laxo porque esto no mide la calidad del HMAC, sino que no haya un
    sesgo estructural de varios por ciento.
    """
    veces = 260_000
    arriba = Counter(mezclar_mazo("seed", "cliente", nonce)[0] for nonce in range(veces))

    assert len(arriba) == 52

    esperado = veces / 52
    peor = max(abs(cuenta - esperado) / esperado for cuenta in arriba.values())
    assert peor < 0.07, "desvio del %.1f por ciento en la carta de arriba" % (peor * 100)


def test_el_muestreo_con_rechazo_no_favorece_a_los_indices_bajos():
    """Directo sobre el helper: 256 % 52 = 48, así que el sesgo sería visible."""
    flujo = flujo_de_bytes("seed", "cliente", 0)
    salidas = Counter(indice_uniforme(flujo, 52) for _ in range(104_000))

    esperado = 104_000 / 52
    bajos = sum(salidas[indice] for indice in range(48))  # los que favorecería
    altos = sum(salidas[indice] for indice in range(48, 52))

    assert abs(bajos / 48 - esperado) / esperado < 0.05
    assert abs(altos / 4 - esperado) / esperado < 0.05


# ------------------------------ el reparto ------------------------------

async def test_la_mano_se_reparte_de_arriba_del_mazo_del_seed():
    """Lo que hace verificable al juego: las cartas son las del mazo comprometido."""
    user_id = await _jugador()
    respuesta = await _mano(user_id)

    async with AsyncSessionLocal() as db:
        semilla = await db.scalar(
            select(GameSeed).where(
                GameSeed.user_id == user_id, GameSeed.game_id == GAME_ID
            )
        )
        fila = await db.get(BlackjackGame, respuesta.game_id)

        mazo = mezclar_mazo(semilla.server_seed, semilla.client_seed, fila.nonce)

        # Como en la mesa: jugador, crupier, jugador, crupier.
        assert fila.player_hand == [mazo[0], mazo[2]]
        assert fila.dealer_hand == [mazo[1], mazo[3]]
        # Y lo que queda por repartir es el resto, en orden.
        assert fila.deck == mazo[4:]


async def test_las_cartas_que_pide_tambien_salen_del_mazo_comprometido():
    user_id = await _jugador()
    respuesta = await _mano(user_id)

    if respuesta.status != "ACTIVE":
        pytest.skip("Salio blackjack natural, no se puede pedir carta")

    async with AsyncSessionLocal() as db:
        await hit_blackjack_service(
            db, user_id, BlackjackAction(game_id=respuesta.game_id)
        )

    async with AsyncSessionLocal() as db:
        semilla = await db.scalar(
            select(GameSeed).where(
                GameSeed.user_id == user_id, GameSeed.game_id == GAME_ID
            )
        )
        fila = await db.get(BlackjackGame, respuesta.game_id)
        mazo = mezclar_mazo(semilla.server_seed, semilla.client_seed, fila.nonce)

        assert fila.player_hand == [mazo[0], mazo[2], mazo[4]]
        assert fila.deck == mazo[5:]


async def test_nunca_se_reparte_la_misma_carta_dos_veces():
    user_id = await _jugador()

    for _ in range(12):
        respuesta = await _mano(user_id)
        await _cerrar(user_id, respuesta)

        async with AsyncSessionLocal() as db:
            fila = await db.get(BlackjackGame, respuesta.game_id)
            repartidas = list(fila.player_hand) + list(fila.dealer_hand)

            assert len(repartidas) == len(set(repartidas))
            assert not set(repartidas) & set(fila.deck)


async def test_cada_mano_consume_un_nonce_distinto():
    user_id = await _jugador()

    nonces = []
    for _ in range(5):
        respuesta = await _mano(user_id)
        nonces.append(respuesta.nonce)
        await _cerrar(user_id, respuesta)

    assert nonces == [1, 2, 3, 4, 5]


# ------------------------------ el compromiso ------------------------------

async def test_la_mano_viene_con_el_hash_pero_no_con_el_seed():
    user_id = await _jugador()

    async with AsyncSessionLocal() as db:
        semilla = await obtener_semilla_blackjack(db, user_id)
        hash_publicado = semilla.server_seed_hash
        server_seed = semilla.server_seed

    respuesta = await _mano(user_id)

    assert respuesta.server_seed_hash == hash_publicado
    assert len(respuesta.server_seed_hash) == 64
    assert respuesta.client_seed
    # El seed no viaja en la respuesta de la mano, por ningun campo.
    assert server_seed not in respuesta.model_dump_json()


async def test_al_rotar_se_revela_el_seed_y_el_hash_cierra():
    user_id = await _jugador()
    respuesta = await _mano(user_id)
    await _cerrar(user_id, respuesta)

    async with AsyncSessionLocal() as db:
        rotada = await rotar_semilla_blackjack(db, user_id, "mi-semilla")

    revelada = rotada["revelada"]
    assert revelada["server_seed_hash"] == respuesta.server_seed_hash
    assert (
        hashlib.sha256(revelada["server_seed"].encode()).hexdigest()
        == respuesta.server_seed_hash
    )
    assert revelada["jugadas"] == 1

    # Y con el seed revelado el mazo de esa mano se rehace.
    mazo = mezclar_mazo(
        revelada["server_seed"], revelada["client_seed"], respuesta.nonce
    )
    assert respuesta.player_hand == [mazo[0], mazo[2]]

    # La nueva arranca limpia y con el client seed que eligio el jugador.
    assert rotada["activa"]["client_seed"] == "mi-semilla"
    assert rotada["activa"]["nonce"] == 0
    assert rotada["activa"]["server_seed_hash"] != respuesta.server_seed_hash


async def test_no_se_puede_revelar_el_seed_con_una_mano_abierta():
    """El exploit que el candado tapa.

    Con el server seed en la mano, el jugador rehace el mazo entero: sabe la
    carta tapada del crupier y que carta le viene si pide. Rotar con la mano en
    curso no seria verificar, seria ver las cartas del otro.
    """
    user_id = await _jugador()
    respuesta = await _mano(user_id)

    if respuesta.status != "ACTIVE":
        pytest.skip("Salio blackjack natural, la mano cerro sola")

    async with AsyncSessionLocal() as db:
        with pytest.raises(HTTPException) as error:
            await rotar_semilla_blackjack(db, user_id)

        assert error.value.status_code == 409

    # Cerrada la mano, si.
    await _cerrar(user_id, respuesta)

    async with AsyncSessionLocal() as db:
        rotada = await rotar_semilla_blackjack(db, user_id)

    assert rotada["revelada"]["server_seed"]


async def test_la_semilla_activa_es_una_sola_y_sobrevive_entre_manos():
    user_id = await _jugador()

    primera = await _mano(user_id)
    await _cerrar(user_id, primera)
    segunda = await _mano(user_id)
    await _cerrar(user_id, segunda)

    assert primera.server_seed_hash == segunda.server_seed_hash

    async with AsyncSessionLocal() as db:
        activas = await db.scalars(
            select(GameSeed).where(
                GameSeed.user_id == user_id,
                GameSeed.game_id == GAME_ID,
                GameSeed.revealed_at.is_(None),
            )
        )
        assert len(list(activas)) == 1


# ------------------------------ la mano abandonada ------------------------------

async def test_la_mano_sin_terminar_se_puede_retomar():
    """La apuesta se debita al repartir: si no se puede retomar, se pierde."""
    user_id = await _jugador()
    respuesta = await _mano(user_id)

    if respuesta.status != "ACTIVE":
        pytest.skip("Salio blackjack natural, la mano cerro sola")

    # Otra sesion, como quien vuelve despues de cerrar la pestana.
    async with AsyncSessionLocal() as db:
        retomada = await obtener_mano_activa(db, user_id)

    assert retomada is not None
    assert retomada.game_id == respuesta.game_id
    assert retomada.player_hand == respuesta.player_hand
    assert retomada.nonce == respuesta.nonce
    # Y la carta tapada del crupier sigue tapada.
    assert retomada.dealer_hand[1] == "HIDDEN"


async def test_sin_mano_abierta_no_hay_nada_que_retomar():
    user_id = await _jugador()

    async with AsyncSessionLocal() as db:
        assert await obtener_mano_activa(db, user_id) is None

    respuesta = await _mano(user_id)
    await _cerrar(user_id, respuesta)

    async with AsyncSessionLocal() as db:
        assert await obtener_mano_activa(db, user_id) is None


async def test_terminar_la_mano_retomada_destraba_la_rotacion():
    """El candado no puede dejar a nadie sin poder verificar para siempre."""
    user_id = await _jugador()
    respuesta = await _mano(user_id)

    if respuesta.status != "ACTIVE":
        pytest.skip("Salio blackjack natural, la mano cerro sola")

    async with AsyncSessionLocal() as db:
        with pytest.raises(HTTPException):
            await rotar_semilla_blackjack(db, user_id)

    # El jugador vuelve, encuentra la mano y la termina.
    async with AsyncSessionLocal() as db:
        abierta = await obtener_mano_activa(db, user_id)

    await _cerrar(user_id, abierta)

    async with AsyncSessionLocal() as db:
        rotada = await rotar_semilla_blackjack(db, user_id)

    assert rotada["revelada"]["server_seed"]
