"""Dice y limbo contra la base: la plata, las semillas y los límites.

Necesitan Postgres, así que corren dentro del contenedor.
"""

import hashlib
from decimal import Decimal

import pytest

try:
    from fastapi import HTTPException
    from sqlalchemy import delete, select, text

    from app.modules.games.dice import reglas as dice_reglas
    from app.modules.games.dice import service as dice
    from app.modules.games.dice.fairness import derivar_salida
    from app.modules.games.limbo import reglas as limbo_reglas
    from app.modules.games.limbo import service as limbo
    from app.modules.games.shared import pagos
    from app.modules.users.infrastructure.models import User
    from app.shared.database import AsyncSessionLocal, engine
except Exception as exc:  # pragma: no cover - entorno sin dependencias
    pytest.skip(
        "Requiere sqlalchemy y Postgres, correr dentro de Docker (%s)" % exc,
        allow_module_level=True,
    )

USERNAME = "test_dice_limbo"
EMAIL = "test_dice_limbo@example.test"
SALDO = Decimal("1000.00")
APUESTA = Decimal("10.00")


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


async def _dice(user_id, objetivo="50.00", lado="menor", apuesta=APUESTA):
    async with AsyncSessionLocal() as db:
        return await dice.jugar(db, user_id, apuesta, objetivo, lado)


async def _limbo(user_id, objetivo="2.00", apuesta=APUESTA):
    async with AsyncSessionLocal() as db:
        return await limbo.jugar(db, user_id, apuesta, objetivo)


# ------------------------------ dice: la plata ------------------------------

async def test_dice_cobra_la_apuesta_y_paga_si_gana():
    user_id = await _jugador()
    estado = await _dice(user_id)

    esperado = SALDO - APUESTA + Decimal(estado["payout"])
    assert await _saldo(user_id) == esperado

    if estado["gano"]:
        assert Decimal(estado["payout"]) > 0
    else:
        assert Decimal(estado["payout"]) == Decimal("0.00")


async def test_dice_el_pago_es_el_multiplicador_exacto():
    user_id = await _jugador()
    estado = await _dice(user_id, objetivo="98.00", lado="menor")

    objetivo = int(Decimal("98.00") * 100)
    multiplicador = dice_reglas.multiplicador_de(objetivo, "menor")

    if estado["gano"]:
        assert Decimal(estado["payout"]) == pagos.premio(APUESTA, multiplicador)


async def test_dice_la_salida_decide_el_resultado():
    """Cruce: se rehace la salida desde la semilla y tiene que coincidir."""
    user_id = await _jugador()
    estado = await _dice(user_id, objetivo="50.00", lado="menor")

    async with AsyncSessionLocal() as db:
        revelado = await dice.rotar_semilla(db, user_id)

    salida = derivar_salida(
        revelado["revelada"]["server_seed"], estado["client_seed"], estado["nonce"]
    )
    assert salida == estado["salida_cruda"]
    assert estado["gano"] == dice_reglas.paga(salida, 5000, "menor")


async def test_dice_varias_jugadas_cierran_la_caja():
    user_id = await _jugador()
    saldo = SALDO

    for _ in range(12):
        estado = await _dice(user_id, objetivo="30.00", lado="menor")
        saldo = saldo - APUESTA + Decimal(estado["payout"])
        assert await _saldo(user_id) == saldo


async def test_dice_sin_saldo_no_juega():
    user_id = await _jugador()

    async with AsyncSessionLocal() as db:
        with pytest.raises(HTTPException):
            await dice.jugar(db, user_id, Decimal("99999.00"), "50.00", "menor")

    assert await _saldo(user_id) == SALDO


async def test_dice_la_apuesta_tiene_tope():
    user_id = await _jugador()

    async with AsyncSessionLocal() as db:
        with pytest.raises(HTTPException) as error:
            await dice.jugar(
                db, user_id, dice.APUESTA_MAXIMA + Decimal("1"), "50.00", "menor"
            )
        assert error.value.status_code == 400

    assert await _saldo(user_id) == SALDO


# ------------------------------ dice: los límites ------------------------------

async def test_dice_rechaza_apuestas_fuera_de_los_limites():
    user_id = await _jugador()

    for objetivo, lado in (("0.00", "menor"), ("99.99", "mayor"), ("99.50", "menor")):
        async with AsyncSessionLocal() as db:
            with pytest.raises(HTTPException) as error:
                await dice.jugar(db, user_id, APUESTA, objetivo, lado)
            assert error.value.status_code == 400

    assert await _saldo(user_id) == SALDO


async def test_dice_rechaza_tres_decimales():
    """El objetivo va en centésimas: aceptar más sería inventar salidas."""
    user_id = await _jugador()

    async with AsyncSessionLocal() as db:
        with pytest.raises(HTTPException) as error:
            await dice.jugar(db, user_id, APUESTA, "50.005", "menor")
        assert error.value.status_code == 400


async def test_dice_cotizar_dice_lo_mismo_que_paga():
    """La pantalla pide el multiplicador, no lo calcula. Tienen que coincidir."""
    user_id = await _jugador()

    cotizacion = dice.cotizar("25.00", "menor")
    estado = await _dice(user_id, objetivo="25.00", lado="menor")

    assert cotizacion["multiplicador"] == estado["multiplicador"]
    assert cotizacion["chance"] == estado["chance"]


async def test_dice_los_limites_publicados_son_los_que_se_aplican():
    limites = dice.tabla_de_limites()

    assert Decimal(limites["multiplicador_maximo"]) == Decimal("990.00")
    assert Decimal(limites["multiplicador_minimo"]) > 1
    assert limites["lados"] == ["menor", "mayor"]


# ------------------------------ limbo ------------------------------

async def test_limbo_cobra_la_apuesta_y_paga_el_objetivo():
    user_id = await _jugador()
    estado = await _limbo(user_id, objetivo="2.00")

    assert await _saldo(user_id) == SALDO - APUESTA + Decimal(estado["payout"])

    if estado["gano"]:
        assert Decimal(estado["payout"]) == APUESTA * 2
        assert float(estado["sorteado"]) >= 2.00
    else:
        assert Decimal(estado["payout"]) == Decimal("0.00")
        assert float(estado["sorteado"]) < 2.00


async def test_limbo_el_sorteado_se_rehace_desde_la_semilla():
    user_id = await _jugador()
    estado = await _limbo(user_id)

    async with AsyncSessionLocal() as db:
        revelado = await limbo.rotar_semilla(db, user_id)

    rehecho = limbo_reglas.calcular_crash_point(
        revelado["revelada"]["server_seed"], estado["client_seed"], estado["nonce"]
    )
    assert "%.2f" % rehecho == estado["sorteado"]


async def test_limbo_rechaza_objetivos_fuera_de_rango():
    user_id = await _jugador()

    for objetivo in ("1.00", "0.50", "1000.01"):
        async with AsyncSessionLocal() as db:
            with pytest.raises(HTTPException) as error:
                await limbo.jugar(db, user_id, APUESTA, objetivo)
            assert error.value.status_code == 400

    assert await _saldo(user_id) == SALDO


async def test_limbo_varias_jugadas_cierran_la_caja():
    user_id = await _jugador()
    saldo = SALDO

    for _ in range(12):
        estado = await _limbo(user_id, objetivo="1.50")
        saldo = saldo - APUESTA + Decimal(estado["payout"])
        assert await _saldo(user_id) == saldo


# ------------------------------ las semillas ------------------------------

async def test_el_nonce_no_se_repite_entre_jugadas():
    """Dos jugadas con el mismo nonce darian la misma salida."""
    user_id = await _jugador()

    nonces = [(await _dice(user_id))["nonce"] for _ in range(6)]
    assert len(set(nonces)) == len(nonces)
    assert nonces == sorted(nonces)


async def test_el_seed_no_se_revela_antes_de_rotar():
    user_id = await _jugador()
    estado = await _dice(user_id)

    assert "server_seed" not in estado
    assert len(estado["server_seed_hash"]) == 64

    async with AsyncSessionLocal() as db:
        revelado = await dice.rotar_semilla(db, user_id)

    # La semilla revelada es la que estuvo vigente; la nueva sólo publica su
    # hash, porque todavía no se jugó nada con ella.
    assert "server_seed" not in revelado["activa"]
    assert revelado["revelada"]["jugadas"] == estado["nonce"]
    assert (
        hashlib.sha256(revelado["revelada"]["server_seed"].encode()).hexdigest()
        == estado["server_seed_hash"]
    )


async def test_cada_juego_tiene_su_semilla():
    """Compartirlas haría que el nonce de uno corriera el del otro."""
    user_id = await _jugador()

    async with AsyncSessionLocal() as db:
        de_dice = await dice.obtener_semilla_activa(db, user_id)
        de_limbo = await limbo.obtener_semilla_activa(db, user_id)

    assert de_dice.id != de_limbo.id
    assert de_dice.game_id == "dice"
    assert de_limbo.game_id == "limbo"


async def test_rotar_deja_una_semilla_nueva_para_seguir_jugando():
    user_id = await _jugador()
    await _dice(user_id)

    async with AsyncSessionLocal() as db:
        revelado = await dice.rotar_semilla(db, user_id)

    estado = await _dice(user_id)

    assert estado["server_seed_hash"] != hashlib.sha256(
        revelado["revelada"]["server_seed"].encode()
    ).hexdigest()
    assert estado["nonce"] == 1


# ------------------------------ el RTP, de punta a punta ------------------------------

async def test_el_rtp_medido_se_acerca_al_declarado():
    """No prueba el RTP —para eso están los tests de reglas, que son exactos—
    pero atrapa que el servicio pague algo distinto de lo que dicen las
    reglas: por ejemplo acreditar de más, o no cobrar la apuesta."""
    user_id = await _jugador()

    apostado = Decimal("0.00")
    pagado = Decimal("0.00")

    for _ in range(150):
        estado = await _dice(user_id, objetivo="50.00", lado="menor", apuesta=Decimal("1.00"))
        apostado += Decimal("1.00")
        pagado += Decimal(estado["payout"])

    assert await _saldo(user_id) == SALDO - apostado + pagado
    # Con 150 jugadas a ~1,98x el ruido es grande; esto sólo descarta
    # un error de orden de magnitud.
    assert Decimal("0.3") < pagado / apostado < Decimal("1.8"), pagado / apostado
