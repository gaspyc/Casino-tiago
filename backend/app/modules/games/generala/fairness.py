"""Provably fair para la generala.

Una partida entera sale de un solo flujo de bytes, consumido en orden:

    bytes = HMAC_SHA256(server_seed, "client_seed:nonce:contador")
    dado  = 1 + (byte % 6), descartando los bytes que sesgarían

El flujo se consume de a un dado por vez, en el orden en que se tiran. Como la
cantidad de dados que saca cada tirada queda determinada por las acciones de
los jugadores, repetir las mismas acciones sobre el mismo seed da exactamente
la misma partida: eso es lo que permite guardar sólo el registro de acciones y
rehacer el estado, igual que en el truco.

El muestreo con rechazo no es un detalle: 256 no es múltiplo de 6, así que
tomar el byte módulo 6 haría salir el 1, el 2, el 3 y el 4 un 1,6% más seguido
que el 5 y el 6. En un juego donde los seises valen el doble que los treses,
eso es plata.
"""

from app.modules.games.generala.dados import CARAS
from app.modules.games.shared.mezcla import flujo_de_bytes, indice_uniforme

__all__ = ["FlujoDeDados", "tirar"]


class FlujoDeDados:
    """Los dados de una partida, en orden y sin repetirse.

    Guarda cuántos lleva tirados para poder rehacer el estado desde cero: dos
    reconstrucciones de la misma partida consumen los mismos bytes.
    """

    def __init__(self, server_seed: str, client_seed: str, nonce: int):
        self._bytes = flujo_de_bytes(server_seed, client_seed, nonce)
        self.tirados = 0

    def tirar(self, cantidad: int) -> list:
        """Los próximos `cantidad` dados del flujo."""
        if cantidad < 0:
            raise ValueError("No se pueden tirar menos de cero dados")

        salida = [1 + indice_uniforme(self._bytes, CARAS) for _ in range(cantidad)]
        self.tirados += cantidad
        return salida


def tirar(server_seed: str, client_seed: str, nonce: int, cantidades) -> list:
    """Rehace una secuencia de tiradas. Para verificar desde afuera."""
    flujo = FlujoDeDados(server_seed, client_seed, nonce)
    return [flujo.tirar(cantidad) for cantidad in cantidades]
