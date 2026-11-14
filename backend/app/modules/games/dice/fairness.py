"""Provably fair para el dice: de dónde sale el número de 0,00 a 99,99.

    firma   = HMAC_SHA256(server_seed, "client_seed:nonce:intento")
    k       = los primeros 52 bits de la firma, en entero
    salida  = k mod 10000

El muestreo con rechazo no es decorativo. 2^52 no es múltiplo de 10.000, así
que tomar el módulo a secas haría salir las primeras 496 salidas una pizca más
seguido que el resto. El sesgo es de 1 en 10^13 —nadie lo notaría jamás— pero
descartarlo cuesta tres líneas y deja el juego exactamente uniforme en vez de
casi uniforme, que para algo que se publica como verificable es la diferencia
entre poder demostrarlo y tener que pedir que te crean.

Cuando el valor cae en la zona a descartar se vuelve a hashear subiendo
`intento`. Pasa una vez cada nueve billones de jugadas, pero el camino está
escrito y probado: si no, sería código que nadie ejecutó nunca decidiendo
plata el día que se ejecute.
"""

import hashlib
import hmac

from app.modules.games.dice.reglas import SALIDAS

__all__ = ["BITS", "derivar_salida"]

BITS = 52
_ESPACIO = 2 ** BITS

# El múltiplo de SALIDAS más grande que entra en el espacio. Lo que queda
# arriba se descarta, que es lo que saca el sesgo del módulo.
_LIMITE = _ESPACIO - (_ESPACIO % SALIDAS)


def derivar_salida(server_seed: str, client_seed: str, nonce: int) -> int:
    """La salida de la jugada, en centésimas: 0 a 9999."""
    for intento in range(64):
        firma = hmac.new(
            server_seed.encode(),
            ("%s:%s:%s" % (client_seed, nonce, intento)).encode(),
            hashlib.sha256,
        ).hexdigest()

        k = int(firma[: BITS // 4], 16)

        if k < _LIMITE:
            return k % SALIDAS

    # Inalcanzable en la práctica: cada intento falla con probabilidad 1e-13.
    raise RuntimeError("No se pudo derivar una salida sin sesgo")
