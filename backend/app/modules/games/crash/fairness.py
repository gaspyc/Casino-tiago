"""Provably fair para Crash.

Antes de que abra la ventana de apuestas el servidor genera un `server_seed` y
publica su SHA-256. El crash point sale de ese seed, o sea que queda fijado
antes de que nadie apueste; cuando la ronda termina se revela el seed y
cualquiera puede rehacer la cuenta y comprobar que el hash coincide:

    firma       = HMAC_SHA256(clave=server_seed, mensaje="client_seed:nonce")
    u           = int(firma[:13], 16) / 2**52        # uniforme en [0, 1)
    crash_point = 1.00 si u > 0.99, si no 0.99 / u   # truncado a 2 decimales

El `client_seed` de cada ronda es el server seed revelado de la ronda anterior:
es público y queda fijado antes de que la ronda empiece.

De ahí sale P(crash >= x) = 0.99 / x, así que cobrar a cualquier multiplicador x
devuelve x * 0.99 / x = 0.99. La ventaja de la casa es 1% para toda estrategia,
y viene entera del 1% de bust instantáneo.

Limitación conocida: el operador todavía podría generar muchos server seeds y
publicar el hash del que más le convenga. Todavía no conoce las apuestas cuando
lo hace, pero puede sesgar la distribución. La solución estándar es una cadena
de hashes generada de una sola vez (se revela en orden inverso, cada seed hashea
al anterior) o un valor público futuro como client seed, tipo el hash de un
bloque de Bitcoin. Es el paso siguiente, no está hecho acá.
"""

import hashlib
import hmac
import math

from app.modules.games.shared.semillas import generar_server_seed, hashear_seed

__all__ = [
    "CLIENT_SEED_INICIAL",
    "MAX_CRASH_POINT",
    "PROBABILIDAD_DE_PAGO",
    "calcular_crash_point",
    "generar_server_seed",
    "hashear_seed",
]

# Techo del multiplicador. No afecta la ventaja de la casa: el juego termina ahí,
# así que tampoco se puede cobrar por encima de este valor.
MAX_CRASH_POINT = 1000.00

# Probabilidad de bust instantáneo. Es toda la ventaja de la casa.
PROBABILIDAD_DE_PAGO = 0.99

# Client seed de la primera ronda, cuando todavía no hay ronda anterior.
CLIENT_SEED_INICIAL = "casino-crash-ronda-inicial"

_BITS = 52


def calcular_crash_point(server_seed: str, client_seed: str, nonce: int) -> float:
    """Deriva el crash point de la ronda. Determinístico y verificable."""
    firma = hmac.new(
        server_seed.encode(),
        ("%s:%s" % (client_seed, nonce)).encode(),
        hashlib.sha256,
    ).hexdigest()

    entero = int(firma[: _BITS // 4], 16)
    u = entero / (2 ** _BITS)

    if u > PROBABILIDAD_DE_PAGO:
        return 1.00

    if u == 0:
        return MAX_CRASH_POINT

    # Se trunca, nunca se redondea para arriba: redondear pagaría de más.
    crash_point = math.floor(PROBABILIDAD_DE_PAGO / u * 100) / 100
    return min(max(crash_point, 1.00), MAX_CRASH_POINT)
