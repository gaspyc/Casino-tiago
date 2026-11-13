"""Mesas de generala entre dos jugadores: la plata, los turnos y el plazo.

Necesitan Postgres, así que corren dentro del contenedor.
"""

import hashlib
from datetime import timedelta
from decimal import Decimal

import pytest

try:
    from fastapi import HTTPException
    from sqlalchemy import delete, select, text

    from app.modules.games.generala import mesas
    from app.modules.games.generala.partida import reconstruir_desde
    from app.modules.games.infrastructure.models import GeneralaMesa
    from app.modules.users.infrastructure.models import User
    from app.shared.database import AsyncSessionLocal, engine
except Exception as exc:  # pragma: no cover - entorno sin dependencias
    pytest.skip(
        "Requiere sqlalchemy y Postgres, correr dentro de Docker (%s)" % exc,
        allow_module_level=True,
    )

ANA = "test_gen_mesa_ana"
BETO = "test_gen_mesa_beto"
CARLA = "test_gen_mesa_carla"
NOMBRES = (ANA, BETO, CARLA)

SALDO = Decimal("300.00")
APUESTA = Decimal("20.00")


async def _limpiar(db):
    await db.execute(
        text(
            "DELETE FROM generala_mesas WHERE jugador_0_id IN "
            "(SELECT id FROM users WHERE username = ANY(:nombres)) "
            "OR jugador_1_id IN (SELECT id FROM users WHERE username = ANY(:nombres))"
        ),
        {"nombres": list(NOMBRES)},
    )
    for tabla in ("transactions", "bets", "generala_partidas"):
        await db.execute(
            text(
                "DELETE FROM %s WHERE user_id IN "
                "(SELECT id FROM users WHERE username = ANY(:nombres))" % tabla
            ),
            {"nombres": list(NOMBRES)},
        )
    await db.execute(delete(User).where(User.username.in_(NOMBRES)))


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


async def _jugadores():
    async with AsyncSessionLocal() as db:
        await _limpiar(db)
        creados = []
        for nombre in NOMBRES:
            user = User(
                username=nombre,
                email=nombre + "@example.test",
                hashed_password="x",
                balance=SALDO,
            )
            db.add(user)
            creados.append(user)
        await db.commit()
        return [user.id for user in creados]


async def _saldo(user_id: int) -> Decimal:
    async with AsyncSessionLocal() as db:
        return await db.scalar(select(User.balance).where(User.id == user_id))


async def _crear(user_id: int, apuesta: Decimal = APUESTA):
    async with AsyncSessionLocal() as db:
        return await mesas.crear_mesa(db, user_id, apuesta)


async def _sentarse(user_id: int, mesa_id: int):
    async with AsyncSessionLocal() as db:
        return await mesas.sentarse(db, user_id, mesa_id)


async def _ver(user_id: int, mesa_id: int):
    async with AsyncSessionLocal() as db:
        return await mesas.ver_mesa(db, user_id, mesa_id)


async def _jugar(user_id: int, mesa_id: int, accion: str):
    async with AsyncSessionLocal() as db:
        return await mesas.jugar(db, user_id, mesa_id, accion)


async def _fila(mesa_id: int) -> GeneralaMesa:
    async with AsyncSessionLocal() as db:
        return await db.get(GeneralaMesa, mesa_id)


async def _mesa_armada(ids):
    """Una mesa con los dos sentados. Devuelve (mesa_id, estado de Ana)."""
    ana, beto = ids[0], ids[1]
    creada = await _crear(ana)
    estado = await _sentarse(beto, creada["mesa_id"])
    return creada["mesa_id"], estado


async def _envejecer(mesa_id: int, segundos: int):
    """Mueve `ultima_accion` para atrás, para no esperar el plazo de verdad."""
    async with AsyncSessionLocal() as db:
        fila = await db.get(GeneralaMesa, mesa_id)
        fila.ultima_accion = mesas._ahora() - timedelta(seconds=segundos)
        await db.commit()


async def _terminar_jugando(ids, mesa_id):
    """Juega la mesa hasta el final anotando siempre la primera disponible."""
    por_asiento = {0: ids[0], 1: ids[1]}
    estado = await _ver(ids[0], mesa_id)

    while not estado["terminada"]:
        turno = estado.get("turno")
        if turno is None:
            break

        quien = por_asiento[estado["en_turno"]]
        anotar = next(a for a in turno["acciones"] if a.startswith("anotar:"))
        estado = await _jugar(quien, mesa_id, anotar)

    return estado


# ------------------------------ crear y sentarse ------------------------------

async def test_crear_mesa_debita_y_queda_esperando():
    ana = (await _jugadores())[0]
    estado = await _crear(ana)

    assert estado["estado"] == mesas.ESPERANDO
    assert estado["asiento"] == 0
    assert estado["pozo"] == "40.00"
    assert estado["turno"] is None
    assert await _saldo(ana) == SALDO - APUESTA


async def test_sentarse_debita_y_arranca_la_partida():
    ids = await _jugadores()
    mesa_id, estado = await _mesa_armada(ids)

    assert estado["estado"] in (mesas.JUGANDO, mesas.TERMINADA)
    assert estado["asiento"] == 1
    assert estado["jugadores"] == [ANA, BETO]
    assert await _saldo(ids[1]) == SALDO - APUESTA

    if estado["estado"] == mesas.JUGANDO:
        assert len(estado["turno"]["dados"]) == 5
        assert estado["totales"] == [0, 0]


async def test_no_se_entra_a_dos_mesas():
    ids = await _jugadores()
    await _crear(ids[0])

    async with AsyncSessionLocal() as db:
        with pytest.raises(HTTPException):
            await mesas.crear_mesa(db, ids[0], APUESTA)

    assert await _saldo(ids[0]) == SALDO - APUESTA


async def test_no_se_sienta_en_su_propia_mesa():
    ids = await _jugadores()
    creada = await _crear(ids[0])

    async with AsyncSessionLocal() as db:
        with pytest.raises(HTTPException):
            await mesas.sentarse(db, ids[0], creada["mesa_id"])


async def test_la_mesa_llena_no_acepta_a_un_tercero():
    ids = await _jugadores()
    mesa_id, _ = await _mesa_armada(ids)

    async with AsyncSessionLocal() as db:
        with pytest.raises(HTTPException) as error:
            await mesas.sentarse(db, ids[2], mesa_id)

        assert error.value.status_code == 400

    assert await _saldo(ids[2]) == SALDO


async def test_sentarse_sin_saldo_no_entra():
    ids = await _jugadores()
    creada = await _crear(ids[0])

    async with AsyncSessionLocal() as db:
        await db.execute(
            text("UPDATE users SET balance = 5 WHERE id = :id"), {"id": ids[1]}
        )
        await db.commit()

    async with AsyncSessionLocal() as db:
        with pytest.raises(HTTPException) as error:
            await mesas.sentarse(db, ids[1], creada["mesa_id"])

        assert error.value.status_code == 400

    assert await _saldo(ids[1]) == Decimal("5.00")
    assert (await _fila(creada["mesa_id"])).estado == mesas.ESPERANDO


async def test_el_de_afuera_no_ve_la_mesa():
    ids = await _jugadores()
    mesa_id, _ = await _mesa_armada(ids)

    async with AsyncSessionLocal() as db:
        with pytest.raises(HTTPException) as error:
            await mesas.ver_mesa(db, ids[2], mesa_id)

        assert error.value.status_code == 403


async def test_el_listado_marca_donde_puedo_sentarme():
    ids = await _jugadores()
    creada = await _crear(ids[0])

    async with AsyncSessionLocal() as db:
        propias = await mesas.listar_mesas(db, ids[0])
        ajenas = await mesas.listar_mesas(db, ids[1])

    mia = next(m for m in propias if m["id"] == creada["mesa_id"])
    suya = next(m for m in ajenas if m["id"] == creada["mesa_id"])

    assert mia["soy_parte"] and not mia["puedo_sentarme"]
    assert not suya["soy_parte"] and suya["puedo_sentarme"]
    assert suya["creador"] == ANA and suya["rival"] is None


# ------------------------------ quién empieza ------------------------------

async def test_quien_empieza_sale_del_seed():
    """Ni el que crea ni el que se sienta lo eligen: lo decide el seed."""
    ids = await _jugadores()
    creada = await _crear(ids[0])
    fila = await _fila(creada["mesa_id"])

    assert fila.empieza == mesas.empieza_segun_seed(
        fila.server_seed, fila.client_seed, fila.nonce
    )
    assert fila.empieza in (0, 1)


async def test_quien_empieza_no_se_publica_antes_de_que_haya_rival():
    ids = await _jugadores()
    creada = await _crear(ids[0])

    assert creada["empieza"] is None

    estado = await _sentarse(ids[1], creada["mesa_id"])
    assert estado["empieza"] in (0, 1)


async def test_derivar_quien_empieza_no_mueve_los_dados():
    """Si compartiera flujo con los dados, derivarlo correría la partida."""
    from app.modules.games.generala.fairness import tirar

    antes = tirar("seed-de-prueba", "cliente", 7, [5, 3, 5])
    mesas.empieza_segun_seed("seed-de-prueba", "cliente", 7)
    despues = tirar("seed-de-prueba", "cliente", 7, [5, 3, 5])

    assert antes == despues


async def test_quien_empieza_es_parejo():
    """Un sesgo acá sería regalarle los 0,3 puntos de arrancar a un asiento."""
    cuenta = [0, 0]
    for nonce in range(2000):
        cuenta[mesas.empieza_segun_seed("seed-fijo", "cliente", nonce)] += 1

    assert abs(cuenta[0] - cuenta[1]) < 150


# ------------------------------ los turnos ------------------------------

async def test_solo_juega_el_que_tiene_el_turno():
    ids = await _jugadores()
    mesa_id, estado = await _mesa_armada(ids)

    if estado["terminada"]:
        pytest.skip("Generala servida en la primera")

    fuera_de_turno = ids[1 - estado["en_turno"]]

    async with AsyncSessionLocal() as db:
        with pytest.raises(HTTPException) as error:
            await mesas.jugar(db, fuera_de_turno, mesa_id, "tirar:0")

        assert error.value.status_code == 400
        assert "turno" in error.value.detail.lower()


async def test_me_toca_es_cierto_para_uno_solo():
    ids = await _jugadores()
    mesa_id, estado = await _mesa_armada(ids)

    if estado["terminada"]:
        pytest.skip("Generala servida en la primera")

    uno = await _ver(ids[0], mesa_id)
    otro = await _ver(ids[1], mesa_id)

    assert uno["me_toca"] != otro["me_toca"]


async def test_la_accion_queda_registrada_con_el_asiento():
    ids = await _jugadores()
    mesa_id, estado = await _mesa_armada(ids)

    if estado["terminada"]:
        pytest.skip("Generala servida en la primera")

    asiento = estado["en_turno"]
    estado = await _jugar(ids[asiento], mesa_id, "tirar:0")

    assert estado["turno"]["tirada"] == 2

    fila = await _fila(mesa_id)
    assert fila.acciones[-1] == {"jugador": asiento, "accion": "tirar:0"}


async def test_una_accion_invalida_no_avanza_la_mesa():
    ids = await _jugadores()
    mesa_id, estado = await _mesa_armada(ids)

    if estado["terminada"]:
        pytest.skip("Generala servida en la primera")

    quien = ids[estado["en_turno"]]
    jugadas = estado["acciones_jugadas"]

    async with AsyncSessionLocal() as db:
        with pytest.raises(HTTPException) as error:
            await mesas.jugar(db, quien, mesa_id, "anotar:escalera_real")

        assert error.value.status_code == 400

    assert len((await _fila(mesa_id)).acciones) == jugadas


async def test_el_turno_pasa_al_otro_al_anotar():
    ids = await _jugadores()
    mesa_id, estado = await _mesa_armada(ids)

    if estado["terminada"]:
        pytest.skip("Generala servida en la primera")

    asiento = estado["en_turno"]
    categoria = next(
        a.split(":", 1)[1]
        for a in estado["turno"]["acciones"]
        if a.startswith("anotar:")
    )
    estado = await _jugar(ids[asiento], mesa_id, "anotar:%s" % categoria)

    if not estado["terminada"]:
        assert estado["en_turno"] == 1 - asiento
        assert estado["planillas"][asiento][categoria] is not None


async def test_no_se_juega_una_mesa_que_espera_rival():
    ids = await _jugadores()
    creada = await _crear(ids[0])

    async with AsyncSessionLocal() as db:
        with pytest.raises(HTTPException) as error:
            await mesas.jugar(db, ids[0], creada["mesa_id"], "tirar:0")

        assert error.value.status_code == 400


# ------------------------------ el plazo de turno ------------------------------

async def test_el_plazo_corre_para_el_que_tiene_que_jugar():
    ids = await _jugadores()
    mesa_id, estado = await _mesa_armada(ids)

    if estado["terminada"]:
        pytest.skip("Generala servida en la primera")

    uno = await _ver(ids[0], mesa_id)
    assert 0 < uno["segundos_restantes"] <= uno["plazo_de_turno"]
    assert not uno["puedo_reclamar"]


async def test_vencido_el_plazo_el_rival_reclama_y_se_lleva_el_pozo():
    """Sin esto, el que va perdiendo nunca tiene que perder: se cuelga."""
    ids = await _jugadores()
    mesa_id, estado = await _mesa_armada(ids)

    if estado["terminada"]:
        pytest.skip("Generala servida en la primera")

    colgado = estado["en_turno"]
    reclama = 1 - colgado

    await _envejecer(mesa_id, int(mesas.PLAZO_DE_TURNO.total_seconds()) + 5)

    vista = await _ver(ids[reclama], mesa_id)
    assert vista["puedo_reclamar"]
    assert vista["segundos_restantes"] == 0

    estado = await _ver(ids[colgado], mesa_id)
    assert not estado["puedo_reclamar"]

    async with AsyncSessionLocal() as db:
        cerrada = await mesas.reclamar(db, ids[reclama], mesa_id)

    assert cerrada["terminada"]
    assert cerrada["ganador"] == reclama
    assert cerrada["motivo"] == mesas.PLAZO_VENCIDO

    premio = Decimal(cerrada["premio"])
    assert await _saldo(ids[reclama]) == SALDO - APUESTA + premio
    assert await _saldo(ids[colgado]) == SALDO - APUESTA


async def test_no_se_reclama_antes_del_plazo():
    ids = await _jugadores()
    mesa_id, estado = await _mesa_armada(ids)

    if estado["terminada"]:
        pytest.skip("Generala servida en la primera")

    async with AsyncSessionLocal() as db:
        with pytest.raises(HTTPException) as error:
            await mesas.reclamar(db, ids[1 - estado["en_turno"]], mesa_id)

        assert error.value.status_code == 400
        assert "plazo" in error.value.detail.lower()


async def test_el_que_tiene_el_turno_no_se_reclama_a_si_mismo():
    """Colgarse y después quedarse con la mesa sería lo mismo que no jugar."""
    ids = await _jugadores()
    mesa_id, estado = await _mesa_armada(ids)

    if estado["terminada"]:
        pytest.skip("Generala servida en la primera")

    await _envejecer(mesa_id, int(mesas.PLAZO_DE_TURNO.total_seconds()) + 5)

    async with AsyncSessionLocal() as db:
        with pytest.raises(HTTPException) as error:
            await mesas.reclamar(db, ids[estado["en_turno"]], mesa_id)

        assert error.value.status_code == 400

    assert (await _fila(mesa_id)).estado == mesas.JUGANDO


async def test_jugar_tarde_se_acepta_mientras_nadie_reclamo():
    """El plazo es el reloj del ajedrez: la bandera la tiene que cantar el otro.

    Si rechazara la jugada tardía, una mesa cuyo rival se fue quedaría trabada
    para siempre con la plata de los dos adentro.
    """
    ids = await _jugadores()
    mesa_id, estado = await _mesa_armada(ids)

    if estado["terminada"]:
        pytest.skip("Generala servida en la primera")

    asiento = estado["en_turno"]
    await _envejecer(mesa_id, int(mesas.PLAZO_DE_TURNO.total_seconds()) + 5)

    estado = await _jugar(ids[asiento], mesa_id, "tirar:0")

    assert estado["turno"]["tirada"] == 2
    # Y el plazo volvió a arrancar.
    assert estado["segundos_restantes"] > 0


async def test_jugar_renueva_el_plazo():
    ids = await _jugadores()
    mesa_id, estado = await _mesa_armada(ids)

    if estado["terminada"]:
        pytest.skip("Generala servida en la primera")

    await _envejecer(mesa_id, int(mesas.PLAZO_DE_TURNO.total_seconds()) - 10)
    antes = (await _ver(ids[0], mesa_id))["segundos_restantes"]

    await _jugar(ids[estado["en_turno"]], mesa_id, "tirar:0")
    despues = (await _ver(ids[0], mesa_id))["segundos_restantes"]

    assert antes < 15 < despues


# ------------------------------ abandonar ------------------------------

async def test_abandonar_esperando_devuelve_la_apuesta():
    ids = await _jugadores()
    creada = await _crear(ids[0])

    async with AsyncSessionLocal() as db:
        cerrada = await mesas.abandonar(db, ids[0], creada["mesa_id"])

    assert cerrada["estado"] == mesas.TERMINADA
    assert cerrada["motivo"] == mesas.ABANDONO
    assert await _saldo(ids[0]) == SALDO


async def test_abandonar_jugando_entrega_la_mesa():
    ids = await _jugadores()
    mesa_id, estado = await _mesa_armada(ids)

    if estado["terminada"]:
        pytest.skip("Generala servida en la primera")

    async with AsyncSessionLocal() as db:
        cerrada = await mesas.abandonar(db, ids[0], mesa_id)

    assert cerrada["terminada"]
    assert cerrada["ganador"] == 1
    assert cerrada["motivo"] == mesas.ABANDONO

    premio = Decimal(cerrada["premio"])
    assert await _saldo(ids[0]) == SALDO - APUESTA
    assert await _saldo(ids[1]) == SALDO - APUESTA + premio


async def test_abandonar_libera_para_otra_mesa():
    ids = await _jugadores()
    creada = await _crear(ids[0])

    async with AsyncSessionLocal() as db:
        await mesas.abandonar(db, ids[0], creada["mesa_id"])

    otra = await _crear(ids[0])
    assert otra["mesa_id"] != creada["mesa_id"]


async def test_una_mesa_terminada_no_se_abandona_de_nuevo():
    ids = await _jugadores()
    creada = await _crear(ids[0])

    async with AsyncSessionLocal() as db:
        await mesas.abandonar(db, ids[0], creada["mesa_id"])

        with pytest.raises(HTTPException):
            await mesas.abandonar(db, ids[0], creada["mesa_id"])


# ------------------------------ la plata ------------------------------

async def test_la_comision_sale_del_pozo_y_el_resto_se_lo_lleva_el_ganador():
    ids = await _jugadores()
    mesa_id, _ = await _mesa_armada(ids)
    estado = await _terminar_jugando(ids, mesa_id)

    pozo = APUESTA * 2
    fila = await _fila(mesa_id)

    if estado["ganador"] is None:
        # Empate: vuelve la apuesta y la casa no cobra nada.
        assert Decimal(fila.comision) == Decimal("0.00")
        assert await _saldo(ids[0]) == SALDO
        assert await _saldo(ids[1]) == SALDO
        return

    assert Decimal(fila.comision) == (pozo * mesas.COMISION).quantize(Decimal("0.01"))
    assert Decimal(fila.premio) + Decimal(fila.comision) == pozo

    perdedor = 1 - estado["ganador"]
    assert await _saldo(ids[estado["ganador"]]) == SALDO - APUESTA + Decimal(fila.premio)
    assert await _saldo(ids[perdedor]) == SALDO - APUESTA


async def test_la_casa_se_queda_exactamente_con_la_comision():
    """Lo que entra menos lo que sale tiene que ser la comisión, nada más."""
    ids = await _jugadores()
    mesa_id, _ = await _mesa_armada(ids)
    await _terminar_jugando(ids, mesa_id)

    fila = await _fila(mesa_id)
    juntos = await _saldo(ids[0]) + await _saldo(ids[1])

    assert juntos == SALDO * 2 - Decimal(fila.comision)


async def test_el_empate_devuelve_la_apuesta_sin_comision():
    """En la generala el empate pasa de verdad; cobrar comisión ahí sería
    quedarse con plata de una mesa que no decidió nada."""
    ids = await _jugadores()
    mesa_id, _ = await _mesa_armada(ids)

    async with AsyncSessionLocal() as db:
        fila = await db.get(GeneralaMesa, mesa_id)
        partida = mesas.reconstruir(fila)
        await mesas._liquidar(db, fila, None, partida, mesas.JUGADA)
        await db.commit()

    fila = await _fila(mesa_id)
    assert Decimal(fila.comision) == Decimal("0.00")
    assert await _saldo(ids[0]) == SALDO
    assert await _saldo(ids[1]) == SALDO


async def test_la_mesa_terminada_no_se_juega_mas():
    ids = await _jugadores()
    mesa_id, _ = await _mesa_armada(ids)
    await _terminar_jugando(ids, mesa_id)

    async with AsyncSessionLocal() as db:
        with pytest.raises(HTTPException):
            await mesas.jugar(db, ids[0], mesa_id, "tirar:0")


async def test_terminada_la_mesa_los_dos_quedan_libres():
    ids = await _jugadores()
    mesa_id, _ = await _mesa_armada(ids)
    await _terminar_jugando(ids, mesa_id)

    async with AsyncSessionLocal() as db:
        assert await mesas.mesa_del_jugador(db, ids[0]) is None
        assert await mesas.mesa_del_jugador(db, ids[1]) is None


async def test_cada_jugador_queda_con_su_apuesta_registrada():
    ids = await _jugadores()
    mesa_id, _ = await _mesa_armada(ids)
    await _terminar_jugando(ids, mesa_id)

    async with AsyncSessionLocal() as db:
        filas = (
            await db.execute(
                text(
                    "SELECT user_id, bet_amount, payout FROM bets "
                    "WHERE game_id = :juego AND user_id = ANY(:ids)"
                ),
                {"juego": mesas.GAME_ID, "ids": ids[:2]},
            )
        ).all()

    assert len(filas) == 2
    assert {fila[0] for fila in filas} == set(ids[:2])
    assert all(Decimal(fila[1]) == APUESTA for fila in filas)


# ------------------------------ verificar ------------------------------

async def test_el_seed_se_revela_recien_al_cerrar_la_mesa():
    ids = await _jugadores()
    mesa_id, estado = await _mesa_armada(ids)

    if not estado["terminada"]:
        assert estado["server_seed"] is None
        assert len(estado["server_seed_hash"]) == 64
        estado = await _terminar_jugando(ids, mesa_id)

    assert estado["server_seed"] is not None
    assert (
        hashlib.sha256(estado["server_seed"].encode()).hexdigest()
        == estado["server_seed_hash"]
    )


async def test_la_partida_de_la_mesa_se_rehace_desde_las_acciones():
    ids = await _jugadores()
    mesa_id, _ = await _mesa_armada(ids)
    estado = await _terminar_jugando(ids, mesa_id)

    fila = await _fila(mesa_id)

    # Lo mismo que puede hacer cualquiera con lo que se publicó al cerrar.
    rehecha = reconstruir_desde(
        fila.server_seed,
        fila.client_seed,
        fila.nonce,
        fila.empieza,
        fila.acciones,
    )

    assert [rehecha.total(0), rehecha.total(1)] == estado["totales"]
    assert rehecha.ganador == estado["ganador"]


async def test_los_dados_estan_a_la_vista_de_los_dos():
    """En la generala no hay información oculta, a diferencia del truco."""
    ids = await _jugadores()
    mesa_id, estado = await _mesa_armada(ids)

    if estado["terminada"]:
        pytest.skip("Generala servida en la primera")

    uno = await _ver(ids[0], mesa_id)
    otro = await _ver(ids[1], mesa_id)

    assert uno["turno"]["dados"] == otro["turno"]["dados"]
    assert uno["planillas"] == otro["planillas"]


# ------------------------------ generala servida al abrir ------------------------------

# Un seed cuya primera tirada son cinco iguales. Buscado a mano una sola vez:
# pasa una vez cada 1296, así que dejarlo al azar sería no probar nunca el
# camino en que la mesa se cierra antes de que nadie toque nada.
SEED_SERVIDA = "28def941f7eb560332194a3122bafeb3425345b01e652b82f8f198b94b0b6ead"
CLIENTE_SERVIDA = "servida"


async def _mesa_con_servida(ids):
    """Una mesa cuyo primer turno es una generala servida."""
    creada = await _crear(ids[0])

    async with AsyncSessionLocal() as db:
        fila = await db.get(GeneralaMesa, creada["mesa_id"])
        fila.server_seed = SEED_SERVIDA
        fila.server_seed_hash = hashlib.sha256(SEED_SERVIDA.encode()).hexdigest()
        fila.client_seed = CLIENTE_SERVIDA
        fila.empieza = mesas.empieza_segun_seed(SEED_SERVIDA, CLIENTE_SERVIDA, 0)
        await db.commit()

    return creada["mesa_id"], await _sentarse(ids[1], creada["mesa_id"])


async def test_la_servida_al_abrir_cierra_la_mesa_al_sentarse():
    """Pasa una vez cada 1296: la mesa termina antes de que nadie juegue."""
    ids = await _jugadores()
    mesa_id, estado = await _mesa_con_servida(ids)

    assert estado["estado"] == mesas.TERMINADA
    assert estado["terminada"]
    # La tirada que ganó queda a la vista: es lo que hay que mostrar.
    assert len(set(estado["turno"]["dados"])) == 1

    fila = await _fila(mesa_id)
    assert fila.ganador == fila.empieza
    assert fila.motivo == mesas.JUGADA

    gana, pierde = fila.ganador, 1 - fila.ganador
    assert await _saldo(ids[gana]) == SALDO - APUESTA + Decimal(fila.premio)
    assert await _saldo(ids[pierde]) == SALDO - APUESTA
    assert Decimal(fila.premio) + Decimal(fila.comision) == APUESTA * 2


async def test_la_servida_al_abrir_no_deja_la_mesa_jugable():
    ids = await _jugadores()
    mesa_id, _ = await _mesa_con_servida(ids)

    async with AsyncSessionLocal() as db:
        with pytest.raises(HTTPException):
            await mesas.jugar(db, ids[0], mesa_id, "tirar:0")

        with pytest.raises(HTTPException):
            await mesas.reclamar(db, ids[0], mesa_id)


async def test_la_servida_al_abrir_revela_el_seed():
    ids = await _jugadores()
    _, estado = await _mesa_con_servida(ids)

    assert estado["server_seed"] == SEED_SERVIDA
    assert estado["generala_servida_de"] == estado["ganador"]


# ------------------------------ el índice que cierra la carrera ------------------------------

async def test_la_base_no_deja_dos_mesas_abiertas_del_mismo_jugador():
    """El chequeo de la aplicación cubre el caso normal; esto cubre la carrera
    de dos pedidos simultáneos, que sin el índice debitaría dos apuestas."""
    from sqlalchemy.exc import IntegrityError

    ids = await _jugadores()
    creada = await _crear(ids[0])

    async with AsyncSessionLocal() as db:
        fila = await db.get(GeneralaMesa, creada["mesa_id"])

        db.add(
            GeneralaMesa(
                jugador_0_id=ids[0],
                apuesta=APUESTA,
                estado=mesas.ESPERANDO,
                server_seed=fila.server_seed,
                server_seed_hash=fila.server_seed_hash,
                client_seed=fila.client_seed,
                nonce=0,
                empieza=0,
                acciones=[],
            )
        )

        with pytest.raises(IntegrityError):
            await db.commit()
