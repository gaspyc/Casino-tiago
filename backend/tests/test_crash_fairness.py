"""Tests del provably fair de Crash y del CSPRNG.

Son unitarios: no tocan la base ni la red.
"""

import hashlib

import pytest

from app.modules.games.crash.fairness import (
    MAX_CRASH_POINT,
    calcular_crash_point,
    generar_server_seed,
    hashear_seed,
)
from app.modules.games.shared import rng

SEED_FIJO = "a" * 64
MUESTRAS = 200_000


def _crash_points(cantidad: int = MUESTRAS):
    """Seeds derivados de forma determinística para que el test no sea flaky."""
    return [
        calcular_crash_point(
            hashlib.sha256(("rtp-%d" % i).encode()).hexdigest(), "cliente", i
        )
        for i in range(cantidad)
    ]


# --------------------------- compromiso y verificación ---------------------------

def test_el_crash_point_es_deterministico():
    """Sin esto no hay nada que verificar: el jugador rehace la cuenta."""
    primero = calcular_crash_point(SEED_FIJO, "cliente-fijo", 1)
    segundo = calcular_crash_point(SEED_FIJO, "cliente-fijo", 1)

    assert primero == segundo


def test_vector_conocido():
    """Fija la fórmula: si cambia, este número cambia y el test avisa."""
    assert calcular_crash_point(SEED_FIJO, "cliente-fijo", 1) == 1.26


def test_el_hash_publicado_corresponde_al_seed_revelado():
    seed = generar_server_seed()

    compromiso = hashear_seed(seed)

    assert compromiso == hashlib.sha256(seed.encode()).hexdigest()
    assert len(compromiso) == 64


def test_el_nonce_cambia_el_resultado():
    resultados = {calcular_crash_point(SEED_FIJO, "cliente", n) for n in range(50)}

    assert len(resultados) > 1


def test_el_client_seed_cambia_el_resultado():
    uno = calcular_crash_point(SEED_FIJO, "cliente-a", 1)
    otro = calcular_crash_point(SEED_FIJO, "cliente-b", 1)

    assert uno != otro


def test_los_server_seeds_no_se_repiten():
    seeds = {generar_server_seed() for _ in range(1000)}

    assert len(seeds) == 1000
    assert all(len(seed) == 64 for seed in seeds)


# --------------------------- distribución y RTP ---------------------------

@pytest.mark.parametrize("objetivo", [1.01, 2.00, 5.00, 10.00])
def test_rtp_del_99_por_ciento_para_cualquier_objetivo(objetivo):
    """La propiedad que hace justo al juego: cobrar a x devuelve x * 0.99 / x.

    Se simula un jugador que siempre cobra al mismo multiplicador.
    """
    crash_points = _crash_points()

    ganadas = sum(1 for punto in crash_points if punto >= objetivo)
    rtp = (ganadas / len(crash_points)) * objetivo

    assert 0.98 < rtp < 1.00


def test_la_probabilidad_sigue_la_formula_teorica():
    crash_points = _crash_points()

    for objetivo in (1.50, 3.00, 20.00):
        observada = sum(1 for punto in crash_points if punto >= objetivo) / len(crash_points)
        teorica = 0.99 / objetivo
        assert abs(observada - teorica) < 0.005


def test_el_crash_point_siempre_esta_en_rango():
    crash_points = _crash_points(20_000)

    assert all(1.00 <= punto <= MAX_CRASH_POINT for punto in crash_points)


def test_hay_bust_instantaneo():
    """Un 1% del bust viene del tope de u, el resto de truncar por debajo de 1.01."""
    crash_points = _crash_points()

    proporcion = sum(1 for punto in crash_points if punto == 1.00) / len(crash_points)

    assert 0.015 < proporcion < 0.025


def test_el_crash_point_se_trunca_nunca_se_redondea_para_arriba():
    """Redondear para arriba pagaría de más en cada ronda."""
    for punto in _crash_points(5_000):
        assert punto == round(punto, 2)


# --------------------------- CSPRNG ---------------------------

def test_el_rng_no_usa_mersenne_twister():
    """`random` es predecible observando resultados; los juegos usan el del sistema."""
    import secrets

    assert isinstance(rng.system_random, secrets.SystemRandom)


def test_shuffle_conserva_las_cartas():
    original = ["%s%s" % (v, p) for p in "abcd" for v in range(13)]
    mezclado = list(original)

    rng.shuffle(mezclado)

    assert sorted(mezclado) == sorted(original)
    assert len(mezclado) == 52


def test_choice_devuelve_un_elemento_de_la_secuencia():
    opciones = list(range(37))

    resultados = {rng.choice(opciones) for _ in range(2000)}

    assert resultados.issubset(set(opciones))
    assert len(resultados) == 37  # con 2000 tiradas salen los 37
