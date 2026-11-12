"""Mazo español y jerarquía del truco argentino.

Una carta se escribe como el valor seguido de la inicial del palo: "1E" es el
ancho de espada, "12O" el rey de oro. El palo es siempre el último carácter,
así que "10B" se lee sin ambigüedad.

La jerarquía no es la del valor: el 1 de espada le gana a todo, el 3 le gana al
2, y el 4 es la carta más baja. Las cartas que comparten escalón empardan.
"""

PALOS = {"E": "espada", "B": "basto", "O": "oro", "C": "copa"}
VALORES = (1, 2, 3, 4, 5, 6, 7, 10, 11, 12)

MAZO = tuple(
    "%s%s" % (valor, palo) for palo in PALOS for valor in VALORES
)

# De mayor a menor. Las cartas de un mismo escalón empardan entre sí.
_ESCALONES = (
    ("1E",),                          # ancho de espada
    ("1B",),                          # ancho de basto
    ("7E",),
    ("7O",),
    ("3E", "3B", "3O", "3C"),
    ("2E", "2B", "2O", "2C"),
    ("1O", "1C"),                     # los anchos falsos
    ("12E", "12B", "12O", "12C"),     # reyes
    ("11E", "11B", "11O", "11C"),     # caballos
    ("10E", "10B", "10O", "10C"),     # sotas
    ("7C", "7B"),                     # los sietes malos
    ("6E", "6B", "6O", "6C"),
    ("5E", "5B", "5O", "5C"),
    ("4E", "4B", "4O", "4C"),
)

# Menor número = carta más fuerte.
JERARQUIA = {
    carta: escalon
    for escalon, cartas in enumerate(_ESCALONES)
    for carta in cartas
}


def valor_de(carta: str) -> int:
    return int(carta[:-1])


def palo_de(carta: str) -> str:
    return carta[-1]


def comparar(una: str, otra: str) -> int:
    """1 si gana la primera, -1 si gana la segunda, 0 si emparda."""
    escalon_una, escalon_otra = JERARQUIA[una], JERARQUIA[otra]

    if escalon_una == escalon_otra:
        return 0

    return 1 if escalon_una < escalon_otra else -1


def carta_mas_alta(cartas) -> str:
    """La más fuerte de las cartas. Si empardan, devuelve la primera."""
    mejor = cartas[0]
    for carta in cartas[1:]:
        if comparar(carta, mejor) > 0:
            mejor = carta

    return mejor


def valor_envido(carta: str) -> int:
    """Para el envido, las figuras valen 0 y el resto su número."""
    valor = valor_de(carta)
    return 0 if valor >= 10 else valor


def puntos_envido(mano) -> int:
    """Los puntos de envido de una mano de tres cartas.

    Con dos o más cartas del mismo palo son las dos más altas de ese palo más
    20. Sin dos del mismo palo, la carta más alta sola.
    """
    por_palo = {}
    for carta in mano:
        por_palo.setdefault(palo_de(carta), []).append(valor_envido(carta))

    mejor = 0
    for valores in por_palo.values():
        if len(valores) >= 2:
            dos_mas_altas = sorted(valores, reverse=True)[:2]
            mejor = max(mejor, sum(dos_mas_altas) + 20)
        else:
            mejor = max(mejor, valores[0])

    return mejor


def tiene_flor(mano) -> bool:
    """Flor es tener las tres cartas del mismo palo."""
    return len({palo_de(carta) for carta in mano}) == 1


def puntos_flor(mano) -> int:
    """La flor vale 20 más la suma de las tres cartas."""
    return 20 + sum(valor_envido(carta) for carta in mano)
