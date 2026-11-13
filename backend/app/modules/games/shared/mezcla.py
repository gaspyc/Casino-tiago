"""Mezcla verificable de cualquier mazo o conjunto de piezas.

Un Fisher-Yates manejado por los bytes de un HMAC, así que el orden resultante
queda determinado por el seed y se puede rehacer después:

    bytes = HMAC_SHA256(server_seed, "client_seed:nonce:contador")

Lo usan el truco (40 cartas españolas), el blackjack (52 inglesas) y el mines
(25 casillas). El sesgo del módulo es el detalle que importa: tomar el byte
módulo el tope le daría ventaja a las primeras posiciones, porque 256 no es
múltiplo de 40, ni de 52, ni de 25. Por eso los índices salen por muestreo con
rechazo.
"""

import hashlib
import hmac

__all__ = ["flujo_de_bytes", "indice_uniforme", "mezclar"]


def flujo_de_bytes(server_seed: str, client_seed: str, nonce: int):
    """Bytes pseudoaleatorios sin límite, encadenando bloques de HMAC."""
    contador = 0
    while True:
        bloque = hmac.new(
            server_seed.encode(),
            ("%s:%s:%s" % (client_seed, nonce, contador)).encode(),
            hashlib.sha256,
        ).digest()

        for byte in bloque:
            yield byte

        contador += 1


def indice_uniforme(flujo, tope: int) -> int:
    """Entero uniforme en [0, tope) descartando los bytes que sesgarían."""
    if tope <= 0:
        raise ValueError("El tope tiene que ser positivo")

    if tope > 256:
        raise ValueError("Este muestreo sirve para topes de hasta 256")

    limite = 256 - (256 % tope)

    for byte in flujo:
        if byte < limite:
            return byte % tope

    raise RuntimeError("El flujo de bytes se agotó")


def mezclar(piezas, server_seed: str, client_seed: str, nonce: int) -> list:
    """Las piezas en un orden determinado por el seed. Verificable."""
    mezclado = list(piezas)
    flujo = flujo_de_bytes(server_seed, client_seed, nonce)

    for posicion in range(len(mezclado) - 1, 0, -1):
        otra = indice_uniforme(flujo, posicion + 1)
        mezclado[posicion], mezclado[otra] = mezclado[otra], mezclado[posicion]

    return mezclado
