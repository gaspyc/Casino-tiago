"""Provably fair para Plinko.

El resultado de una bola es la secuencia de lados que toma en cada fila, y esa
secuencia sale de un HMAC, no de la física:

    firma  = HMAC_SHA256(clave=server_seed, mensaje="client_seed:nonce")
    fila i = "R" si el byte i de la firma es impar, "L" si es par
    slot   = cantidad de "R"

El server seed se compromete por hash antes de la primera bola, y el jugador
elige su propio client seed. Cuando quiere verificar pide la rotación de la
semilla: el servidor revela la vieja y cualquiera puede rehacer el camino de
todas las bolas que jugó con ella, nonce por nonce.

Que el slot sea la cantidad de "R" hace que la distribución sea **exactamente**
binomial, que es la que la tabla de pagos ya daba por supuesta al calcular los
multiplicadores con C(filas, slot) / 2^filas. La simulación física anterior no
lo era: el clamp de los bordes metía en los slots extremos, que son los de mayor
multiplicador, toda bola que se pasaba de rango. Medido sobre 40.000 tiros de 12
filas, los slots 0 y 12 salían 34 y 37 veces más seguido que la binomial, y el
RTP real era 99.5% en riesgo bajo, 110% en medio y 177% en alto.
"""

import hashlib
import hmac

from app.modules.games.shared.semillas import (
    generar_client_seed,
    generar_server_seed,
    hashear_seed,
)

__all__ = [
    "MAX_FILAS",
    "derivar_camino",
    "generar_client_seed",
    "generar_server_seed",
    "hashear_seed",
    "slot_desde_camino",
]

# Un byte de la firma por fila, y la firma tiene 32.
MAX_FILAS = 32


def derivar_camino(server_seed: str, client_seed: str, nonce: int, filas: int) -> list:
    """Los lados que toma la bola. Determinístico y verificable."""
    if filas > MAX_FILAS:
        raise ValueError("No se pueden derivar más de %s filas" % MAX_FILAS)

    firma = hmac.new(
        server_seed.encode(),
        ("%s:%s" % (client_seed, nonce)).encode(),
        hashlib.sha256,
    ).digest()

    # 256 es par, así que la paridad del byte no tiene sesgo hacia ningún lado.
    return ["R" if firma[fila] % 2 else "L" for fila in range(filas)]


def slot_desde_camino(camino: list) -> int:
    """El slot es la cantidad de veces que la bola fue para la derecha."""
    return camino.count("R")
