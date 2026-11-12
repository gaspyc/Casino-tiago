"""Reglas de puntaje y resolución de la mano en el truco argentino.

Todo lo de acá es puro: entra el estado de una mano y salen puntos. El servicio
que maneje la mesa decide cuándo llamarlo.
"""

PUNTOS_PARTIDA = 30
PUNTOS_MALAS = 15

# Resultado de cada una de las tres manos.
GANA_MANO = "mano"      # ganó el que reparte segundo, el "mano"
GANA_PIE = "pie"        # ganó el otro
PARDA = "parda"

# Lo que vale cada canto de truco si se quiere. Sin cantar nada, la mano vale 1.
VALOR_TRUCO = {"truco": 2, "retruco": 3, "vale_cuatro": 4}
ESCALERA_TRUCO = ("truco", "retruco", "vale_cuatro")

# Lo que suma cada canto de envido. La falta se calcula aparte.
VALOR_ENVIDO = {"envido": 2, "real_envido": 3}
ESCALERA_ENVIDO = ("envido", "real_envido", "falta_envido")

VALOR_FLOR = 3
VALOR_CONTRAFLOR = 6


def ganador_de_la_mano(resultados, mano: str = GANA_MANO) -> str:
    """Quién se lleva la mano según cómo salieron las tres.

    `resultados` son los resultados de cada mano jugada, en orden. `mano` es
    quién es mano, que es el que gana cuando todo emparda.

    Las pardas son la parte que todo el mundo discute:
    - Parda la primera, gana el que gane la segunda; si también emparda, el que
      gane la tercera; si empardan las tres, el mano.
    - Gana la primera y emparda la segunda, gana el que ganó la primera.
    - Si cada uno ganó una y emparda la tercera, gana el que ganó la primera.
    """
    if not resultados:
        return None

    primera = resultados[0]

    if primera != PARDA:
        if len(resultados) < 2:
            return None

        segunda = resultados[1]

        # Ganó las dos, o ganó la primera y empardó la segunda.
        if segunda in (primera, PARDA):
            return primera

        if len(resultados) < 3:
            return None

        tercera = resultados[2]

        # Una cada uno: si la tercera emparda, manda la primera.
        return primera if tercera == PARDA else tercera

    # Parda la primera: define la siguiente que no emparde.
    for resultado in resultados[1:]:
        if resultado != PARDA:
            return resultado

    return mano if len(resultados) == 3 else None


def puntos_truco(cantos, querido: bool) -> int:
    """Cuánto vale la mano según hasta dónde llegó el canto.

    Sin cantos vale 1. Si no se quiere, se paga lo que valía antes del último
    canto: truco no querido paga 1, retruco no querido 2, vale cuatro 3.
    """
    if not cantos:
        return 1

    _validar_escalera(cantos, ESCALERA_TRUCO, "truco")

    if querido:
        return VALOR_TRUCO[cantos[-1]]

    return VALOR_TRUCO[cantos[-2]] if len(cantos) > 1 else 1


def puntos_envido(cantos, querido: bool, puntos_a: int = 0, puntos_b: int = 0) -> int:
    """Cuánto vale el envido cantado.

    Querido suma todos los cantos. No querido paga lo acumulado antes del
    último, con un mínimo de 1: envido solo no querido paga 1, envido envido no
    querido paga 2.

    La falta envido querida vale lo que le falta al que va ganando para salir.
    """
    if not cantos:
        return 0

    _validar_escalera(cantos, ESCALERA_ENVIDO, "envido")

    if not querido:
        return max(_acumulado(cantos[:-1]), 1)

    if cantos[-1] == "falta_envido":
        return puntos_de_la_falta(puntos_a, puntos_b)

    return _acumulado(cantos)


def puntos_de_la_falta(puntos_a: int, puntos_b: int) -> int:
    """Lo que le falta al que va ganando para llegar a 30."""
    return max(PUNTOS_PARTIDA - max(puntos_a, puntos_b), 1)


def _acumulado(cantos) -> int:
    return sum(VALOR_ENVIDO[canto] for canto in cantos)


def _validar_escalera(cantos, escalera, nombre: str) -> None:
    """Los cantos tienen que subir sin saltear ni repetir."""
    anterior = -1
    for canto in cantos:
        if canto not in escalera:
            raise ValueError("'%s' no es un canto de %s" % (canto, nombre))

        posicion = escalera.index(canto)

        # El envido se puede repetir ("envido, envido"), el truco no.
        if nombre == "envido":
            if canto != "envido" and posicion <= anterior:
                raise ValueError("Los cantos de envido tienen que subir")
        elif posicion != anterior + 1:
            raise ValueError("Los cantos de truco tienen que subir de a uno")

        anterior = max(anterior, posicion)


def gana_el_envido(puntos_jugador: int, puntos_rival: int, jugador_es_mano: bool) -> bool:
    """Con los mismos puntos gana el mano."""
    if puntos_jugador != puntos_rival:
        return puntos_jugador > puntos_rival

    return jugador_es_mano
