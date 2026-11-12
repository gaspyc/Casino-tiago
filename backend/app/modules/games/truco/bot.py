"""El rival de la casa.

Juega con heurísticas, no con búsqueda: mide la fuerza de sus cartas y los
tantos, y decide con umbrales. Los umbrales están arriba y sueltos a propósito,
porque son la perilla con la que se calibra cuánto gana la casa.

Importante para el negocio: contra la casa, la ventaja no sale de una tabla de
pagos sino de que el bot juegue mejor que el jugador. Un humano que sabe le
gana a esto, así que el multiplicador de pago y los límites de apuesta se fijan
midiendo, no suponiendo. `simular.py` hace esa medición.
"""

from app.modules.games.truco import reglas
from app.modules.games.truco.cartas import (
    JERARQUIA,
    comparar,
    puntos_envido,
    tantos_de_flor,
)
from app.modules.games.truco.mano import IRSE_AL_MAZO, NO_QUIERO, QUIERO
from app.modules.games.shared import rng

ESCALONES = 13  # la peor carta está en el escalón 13

# Tantos a partir de los cuales canta envido, y a partir de los cuales lo quiere.
CANTA_ENVIDO = 26
QUIERE_ENVIDO = {"envido": 23, "real_envido": 27, "falta_envido": 29}

# Fuerza de mano (0 a 1) para cantar y para querer el truco.
CANTA_TRUCO = 0.62
QUIERE_TRUCO = 0.42
SUBE_TRUCO = 0.78

# Tantos de flor a partir de los cuales sube a contraflor en vez de aceptar.
SUBE_LA_FLOR = 31

# Cuánto se anima de más cuando tiene flor. No es que las cartas sean mejores:
# medido sobre las 9880 manos posibles, la fuerza media de truco de una mano
# con flor es 0.3962, idéntica a la del resto. Lo que cambia es el riesgo, que
# los 3 puntos de la flor amortiguan: perder un truco cantado cuesta 2 y ya hay
# 3 cobrados.
#
# Medido en 3700 partidas con flor contra el mismo bot sin la bonificación:
# gana 51.9%, unas 2.3 sigmas sobre el azar. Es poco porque la flor sale en el
# 4.86% de las manos. Entre 0.35 y 0.85 no hay diferencia medible, así que
# queda en 0.35: con 0.60 o más cantaría truco siempre que tiene flor, y eso es
# un tell que un humano lee en dos manos.
BONIFICACION_POR_FLOR = 0.35

# Cada tanto manda una mano fuerte como si fuera débil, para no ser legible.
PROBABILIDAD_DE_MENTIR = 0.12


def fuerza_de_carta(carta: str) -> float:
    """1.0 es el ancho de espada, 0.0 un cuatro."""
    return (ESCALONES - JERARQUIA[carta]) / ESCALONES


def fuerza_de_mano(cartas) -> float:
    if not cartas:
        return 0.0

    return sum(fuerza_de_carta(carta) for carta in cartas) / len(cartas)


def decidir(mano, jugador: int):
    """La acción que juega el bot, o None si no tiene nada que hacer."""
    acciones = mano.acciones(jugador)
    if not acciones:
        return None

    if mano.pendiente is not None:
        return _responder(mano, jugador, acciones)

    canto = _buscar_canto(mano, jugador, acciones)
    if canto is not None:
        return canto

    return "jugar:%s" % _elegir_carta(mano, jugador)


# ------------------------------ respuestas ------------------------------

def _responder(mano, jugador: int, acciones: list):
    familia = mano.pendiente["familia"]

    # Con flor en la mano no hay nada que decidir: se canta y mata el envido.
    if "flor" in acciones:
        return "flor"

    if familia == "flor":
        return _responder_flor(mano, jugador, acciones)

    if familia == "envido":
        return _responder_envido(mano, jugador, acciones)

    return _responder_truco(mano, jugador, acciones)


def _responder_flor(mano, jugador: int, acciones: list):
    """Con una flor alta conviene subir; con una baja, que sean buenas."""
    mios = tantos_de_flor(mano._cartas_repartidas(jugador))

    if mios >= SUBE_LA_FLOR:
        for canto in ("contraflor", "contraflor_al_resto"):
            if canto in acciones:
                return canto

        if QUIERO in acciones:
            return QUIERO

    return QUIERO if QUIERO in acciones and mios >= 27 else NO_QUIERO


def _responder_envido(mano, jugador: int, acciones: list):
    tantos = _tantos(mano, jugador)
    canto = mano.pendiente["canto"]

    # Con muy buenos tantos conviene subir antes que aceptar.
    if tantos >= 30 and "real_envido" in acciones:
        return "real_envido"

    return QUIERO if tantos >= QUIERE_ENVIDO.get(canto, 27) else NO_QUIERO


def _responder_truco(mano, jugador: int, acciones: list):
    fuerza = _fuerza_en_juego(mano, jugador)

    subidas = [canto for canto in reglas.ESCALERA_TRUCO if canto in acciones]
    if fuerza >= SUBE_TRUCO and subidas:
        return subidas[0]

    return QUIERO if fuerza >= QUIERE_TRUCO else NO_QUIERO


# ------------------------------ cantos ------------------------------

def _buscar_canto(mano, jugador: int, acciones: list):
    # La flor son tres puntos regalados: se canta siempre.
    if "flor" in acciones:
        return "flor"

    envido = [canto for canto in reglas.ESCALERA_ENVIDO if canto in acciones]
    if envido and _tantos(mano, jugador) >= CANTA_ENVIDO:
        return envido[0]

    truco = [canto for canto in reglas.ESCALERA_TRUCO if canto in acciones]
    if truco and not mano.cantos_truco:
        fuerza = _fuerza_en_juego(mano, jugador)
        if fuerza >= CANTA_TRUCO or (fuerza <= 0.2 and _miente()):
            return truco[0]

    return None


def _miente() -> bool:
    return rng.uniform(0, 1) < PROBABILIDAD_DE_MENTIR


# ------------------------------ las cartas ------------------------------

def _elegir_carta(mano, jugador: int) -> str:
    mis_cartas = mano.cartas[jugador]
    ronda = mano.ronda_actual

    if ronda and len(ronda) == 1:
        return _responder_carta(mis_cartas, ronda[0][1])

    # Sale el bot: manda la más alta en la primera y la más alta que le quede
    # después, que es lo que más veces gana sin pensar de más.
    return _mas_alta(mis_cartas)


def _responder_carta(mis_cartas, carta_rival: str) -> str:
    """La más barata que gane; si ninguna gana, se tira la peor."""
    ganadoras = [carta for carta in mis_cartas if comparar(carta, carta_rival) > 0]

    if ganadoras:
        return _mas_baja(ganadoras)

    return _mas_baja(mis_cartas)


def _mas_alta(cartas) -> str:
    return min(cartas, key=lambda carta: JERARQUIA[carta])


def _mas_baja(cartas) -> str:
    return max(cartas, key=lambda carta: JERARQUIA[carta])


# ------------------------------ auxiliares ------------------------------

def _tantos(mano, jugador: int) -> int:
    jugadas = [
        carta for ronda in mano.rondas for quien, carta in ronda if quien == jugador
    ]
    return puntos_envido(mano.cartas[jugador] + jugadas)


def _fuerza_en_juego(mano, jugador: int) -> float:
    """Con cuánta confianza juega el truco, no qué tan buenas son las cartas.

    Mezcla la fuerza de lo que le queda con cómo viene la mano y con la flor,
    que no mejora las cartas pero abarata perder.
    """
    fuerza = fuerza_de_mano(mano.cartas[jugador])

    ganadas = sum(1 for resultado in mano.resultados if resultado == jugador)
    perdidas = sum(
        1 for resultado in mano.resultados if resultado not in (jugador, reglas.PARDA)
    )

    confianza = fuerza + 0.25 * ganadas - 0.25 * perdidas

    if mano.tiene_flor(jugador):
        confianza += BONIFICACION_POR_FLOR

    return max(0.0, min(1.0, confianza))
