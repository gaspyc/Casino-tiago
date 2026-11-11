"""Estado compartido de la ronda de Crash, en Redis.

El juego dejó de vivir en la memoria de un proceso. Ahora:

- Cualquier worker puede atender el WebSocket de un jugador.
- Un solo proceso corre el game loop: el que gana el lock `crash:lider`.
- Las apuestas y los cashouts se registran en Redis con scripts Lua, que son
  atómicos, así que no hay forma de apostar dos veces ni de cobrar después de
  que explotó.

Claves:
    crash:lider     lock con TTL del proceso que corre el loop
    crash:nonce     contador de rondas, atómico (INCR)
    crash:ultimo_seed  server seed de la última ronda que llegó a terminar
    crash:ronda     hash público de la ronda en curso
    crash:secreto   crash point, seed y momento del crash; nunca se publica
    crash:apuestas  hash user_id -> apuesta
    crash:cashouts  hash user_id -> timestamp del cashout
    crash:eventos   canal pub/sub con el estado que va a los WebSockets

Los datos que revelarían el resultado viven en una clave aparte a propósito: si
el estado público se arma desde `crash:ronda`, no hay manera de filtrarlos por
descuido.
"""

import json
import math

CLAVE_LIDER = "crash:lider"
CLAVE_NONCE = "crash:nonce"
CLAVE_ULTIMO_SEED = "crash:ultimo_seed"
CLAVE_RONDA = "crash:ronda"
CLAVE_SECRETO = "crash:secreto"
CLAVE_APUESTAS = "crash:apuestas"
CLAVE_CASHOUTS = "crash:cashouts"
CANAL_EVENTOS = "crash:eventos"

# El multiplicador crece exponencialmente con el tiempo de vuelo.
RITMO = 0.06

TTL_LIDERAZGO_MS = 15_000
SEGUNDOS_ENTRE_RENOVACIONES = 3.0
SEGUNDOS_ENTRE_INTENTOS_DE_LIDERAZGO = 2.0


# Tomar el liderazgo: lo agarra si está libre y lo renueva si ya era nuestro.
# Sin la segunda parte, el líder no podía encadenar rondas: al terminar una, su
# propio lock seguía vivo y el SET NX fallaba hasta que expiraba el TTL.
LUA_TOMAR_LIDERAZGO = """
if redis.call('SET', KEYS[1], ARGV[1], 'NX', 'PX', ARGV[2]) then return 1 end
if redis.call('GET', KEYS[1]) == ARGV[1] then
    redis.call('PEXPIRE', KEYS[1], ARGV[2])
    return 1
end
return 0
"""

# El lock sólo se renueva si sigue siendo nuestro: si expiró y lo tomó otro
# proceso, no se lo pisamos.
LUA_RENOVAR_LIDERAZGO = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('PEXPIRE', KEYS[1], ARGV[2])
end
return 0
"""

# Registrar la apuesta: la fase, la ronda y el "una sola apuesta por jugador"
# se validan adentro del script, así que no hay ventana entre chequear y grabar.
LUA_APOSTAR = """
if redis.call('HGET', KEYS[1], 'fase') ~= 'BETTING' then return 0 end
if redis.call('HGET', KEYS[1], 'nonce') ~= ARGV[1] then return 0 end
return redis.call('HSETNX', KEYS[2], ARGV[2], ARGV[3])
"""

# Cobrar: el reloj lo pone Redis, no el worker, así que no hay diferencia de
# hora entre procesos. Se compara contra el momento exacto del crash y se graba
# el timestamp; el multiplicador lo deriva la liquidación con ese timestamp.
LUA_COBRAR = """
if redis.call('HGET', KEYS[1], 'fase') ~= 'IN_PROGRESS' then return '' end
if redis.call('HEXISTS', KEYS[2], ARGV[1]) == 0 then return '' end

local crash_ts = redis.call('HGET', KEYS[3], 'crash_ts')
if not crash_ts then return '' end

local t = redis.call('TIME')
local ahora = tonumber(t[1]) + tonumber(t[2]) / 1000000
if ahora >= tonumber(crash_ts) then return '' end

if redis.call('HSETNX', KEYS[4], ARGV[1], tostring(ahora)) == 0 then return '' end
return tostring(ahora)
"""


def multiplicador_en(momento: float, arranque: float) -> float:
    """Multiplicador que mostraba el juego en ese instante del vuelo.

    Trunca a dos decimales: redondear para arriba pagaría más de lo que el
    jugador vio en pantalla.
    """
    if momento <= arranque:
        return 1.00
    return math.floor(math.exp(RITMO * (momento - arranque)) * 100) / 100


def tiempo_de_vuelo(crash_point: float) -> float:
    """Cuántos segundos tarda el multiplicador en llegar al crash point."""
    if crash_point <= 1.0:
        return 0.0
    return math.log(crash_point) / RITMO


def _a_float(valor, por_defecto: float = 0.0) -> float:
    try:
        return float(valor)
    except (TypeError, ValueError):
        return por_defecto


def armar_estado_publico(ronda: dict, apuestas: dict, cashouts: dict) -> dict:
    """El payload que ven los jugadores.

    Se arma sólo con `crash:ronda`, que no contiene el crash point ni el seed
    hasta que la ronda terminó.
    """
    fase = ronda.get("fase", "BETTING")
    arranque = _a_float(ronda.get("arranque_ts"))

    bets = []
    for user_id, crudo in apuestas.items():
        apuesta = json.loads(crudo)
        cashout_ts = cashouts.get(user_id)

        cashout_multiplier = None
        payout = 0.0
        if cashout_ts is not None:
            cashout_multiplier = multiplicador_en(float(cashout_ts), arranque)
            payout = round(apuesta["bet_amount"] * cashout_multiplier, 2)

        bets.append(
            {
                "user_id": int(user_id),
                "username": apuesta["username"],
                "bet_amount": apuesta["bet_amount"],
                "cashout_multiplier": cashout_multiplier,
                "payout": payout,
            }
        )

    bets.sort(key=lambda apuesta: apuesta["user_id"])

    return {
        "status": fase,
        "multiplier": _a_float(ronda.get("multiplicador"), 1.00),
        "timer": _a_float(ronda.get("timer")),
        "bets": bets,
        "server_seed_hash": ronda.get("server_seed_hash"),
        "client_seed": ronda.get("client_seed"),
        "nonce": int(_a_float(ronda.get("nonce"))),
        # Los dos campos siguientes sólo existen en el hash una vez que la ronda
        # terminó: durante el vuelo ni siquiera están para filtrarse.
        "server_seed": ronda.get("server_seed"),
        "crash_point": _a_float(ronda["crash_point"]) if "crash_point" in ronda else None,
    }
