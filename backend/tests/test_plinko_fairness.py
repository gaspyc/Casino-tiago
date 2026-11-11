"""Tests del provably fair de Plinko.

Son unitarios: el módulo de fairness no toca base ni red.
"""

import hashlib
from collections import Counter

import pytest

from app.modules.games.plinko.fairness import (
    MAX_FILAS,
    derivar_camino,
    generar_client_seed,
    generar_server_seed,
    hashear_seed,
    slot_desde_camino,
)

SEED_FIJO = "a" * 64
FILAS = 12
MUESTRAS = 20_000


def _caminos(cantidad: int = MUESTRAS, filas: int = FILAS):
    return [
        derivar_camino(SEED_FIJO, "cliente", nonce, filas) for nonce in range(cantidad)
    ]


# --------------------------- compromiso y verificación ---------------------------

def test_el_camino_es_deterministico():
    """Sin esto no hay nada que verificar: el jugador rehace la cuenta."""
    uno = derivar_camino(SEED_FIJO, "cliente", 1, FILAS)
    otro = derivar_camino(SEED_FIJO, "cliente", 1, FILAS)

    assert uno == otro


def test_vector_conocido():
    """Fija la derivación: si cambia, este camino cambia y el test avisa."""
    assert derivar_camino(SEED_FIJO, "cliente", 1, FILAS) == list("LLRRRRRLRLRR")


def test_el_hash_publicado_corresponde_al_seed_revelado():
    seed = generar_server_seed()

    assert hashear_seed(seed) == hashlib.sha256(seed.encode()).hexdigest()
    assert len(hashear_seed(seed)) == 64


def test_el_nonce_cambia_el_camino():
    caminos = {tuple(derivar_camino(SEED_FIJO, "cliente", n, FILAS)) for n in range(50)}

    assert len(caminos) > 40  # con 4096 combinaciones casi no hay repetidos


def test_el_client_seed_cambia_el_camino():
    caminos = {
        tuple(derivar_camino(SEED_FIJO, "cliente-%d" % i, 1, FILAS)) for i in range(50)
    }

    assert len(caminos) > 40


def test_el_server_seed_cambia_el_camino():
    caminos = {
        tuple(derivar_camino(generar_server_seed(), "cliente", 1, FILAS))
        for _ in range(50)
    }

    assert len(caminos) > 40


def test_los_seeds_no_se_repiten():
    seeds = {generar_server_seed() for _ in range(1000)}
    clientes = {generar_client_seed() for _ in range(1000)}

    assert len(seeds) == 1000
    assert all(len(seed) == 64 for seed in seeds)
    assert len(clientes) == 1000


# --------------------------- forma del camino ---------------------------

@pytest.mark.parametrize("filas", range(8, 17))
def test_el_camino_tiene_una_decision_por_fila(filas):
    camino = derivar_camino(SEED_FIJO, "cliente", 1, filas)

    assert len(camino) == filas
    assert set(camino) <= {"L", "R"}


def test_el_slot_es_la_cantidad_de_derechas():
    assert slot_desde_camino(list("RRRR")) == 4
    assert slot_desde_camino(list("LLLL")) == 0
    assert slot_desde_camino(list("LRLR")) == 2


def test_no_se_pueden_derivar_mas_filas_que_bytes_de_firma():
    """La firma tiene 32 bytes y se usa uno por fila."""
    with pytest.raises(ValueError):
        derivar_camino(SEED_FIJO, "cliente", 1, MAX_FILAS + 1)


# --------------------------- distribución ---------------------------

def test_cada_fila_va_para_cada_lado_la_mitad_de_las_veces():
    """La paridad de un byte no tiene sesgo: 256 es par."""
    caminos = _caminos()

    for fila in range(FILAS):
        derechas = sum(1 for camino in caminos if camino[fila] == "R")
        assert abs(derechas / len(caminos) - 0.5) < 0.02


def test_la_distribucion_de_slots_es_binomial():
    """Es la distribución que la tabla de pagos da por supuesta.

    La simulación física anterior no la producía: acumulaba masa en los slots
    extremos, que son los de mayor multiplicador.
    """
    from math import comb

    conteo = Counter(slot_desde_camino(camino) for camino in _caminos())

    for slot in range(FILAS + 1):
        esperada = comb(FILAS, slot) / (2 ** FILAS)
        observada = conteo[slot] / MUESTRAS
        assert abs(observada - esperada) < 0.015
