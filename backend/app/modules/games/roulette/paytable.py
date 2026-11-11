"""Pagos de la ruleta europea.

Vive separada del servicio para que el RTP se pueda medir sin base de datos.

Los 37 números son equiprobables, así que el RTP de cada tipo de apuesta sale
exacto enumerando la rueda entera. Con estos multiplicadores da 36/37 = 97.30%
para todos por igual, que es lo correcto para la ruleta europea de un solo cero:
ninguna apuesta es mejor que otra, y la ventaja de la casa (2.70%) sale del cero.

Los multiplicadores son brutos, incluyen la apuesta: 36x a pleno es el 35:1 de
la mesa más la ficha devuelta.
"""

from decimal import Decimal

ROULETTE_NUMBERS = list(range(37))
RED_NUMBERS = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}

MULTIPLICADOR_PLENO = Decimal("36.0")
MULTIPLICADOR_SPLIT = Decimal("18.0")
MULTIPLICADOR_CORNER = Decimal("9.0")
MULTIPLICADOR_DOCENA = Decimal("3.0")
MULTIPLICADOR_COLUMNA = Decimal("3.0")
MULTIPLICADOR_CHANCE_SIMPLE = Decimal("2.0")
SIN_PREMIO = Decimal("0.0")


def color_de(numero: int) -> str:
    if numero == 0:
        return "green"
    return "red" if numero in RED_NUMBERS else "black"


def paridad_de(numero: int) -> str:
    if numero == 0:
        return "none"
    return "even" if numero % 2 == 0 else "odd"


def docena_de(numero: int) -> int:
    return (numero - 1) // 12 + 1


def columna_de(numero: int) -> int:
    return (numero - 1) % 3 + 1


def mitad_de(numero: int) -> str:
    return "low" if numero <= 18 else "high"


def calcular_multiplicador(bet_type: str, bet_value: str, numero_ganador: int) -> Decimal:
    """Cuánto paga una apuesta contra el número que salió. 0 si perdió.

    `bet_value` llega ya validado y normalizado por el schema.
    """
    if bet_type == "number":
        return MULTIPLICADOR_PLENO if str(numero_ganador) == bet_value else SIN_PREMIO

    if bet_type == "color":
        return (
            MULTIPLICADOR_CHANCE_SIMPLE
            if color_de(numero_ganador) == bet_value.lower()
            else SIN_PREMIO
        )

    if bet_type == "parity":
        return (
            MULTIPLICADOR_CHANCE_SIMPLE
            if paridad_de(numero_ganador) == bet_value.lower()
            else SIN_PREMIO
        )

    if bet_type == "split":
        return (
            MULTIPLICADOR_SPLIT
            if str(numero_ganador) in bet_value.split(",")
            else SIN_PREMIO
        )

    if bet_type == "corner":
        return (
            MULTIPLICADOR_CORNER
            if str(numero_ganador) in bet_value.split(",")
            else SIN_PREMIO
        )

    # El cero no paga ninguna de las apuestas externas.
    if numero_ganador == 0:
        return SIN_PREMIO

    if bet_type == "dozen":
        return (
            MULTIPLICADOR_DOCENA
            if str(docena_de(numero_ganador)) == bet_value
            else SIN_PREMIO
        )

    if bet_type == "column":
        return (
            MULTIPLICADOR_COLUMNA
            if str(columna_de(numero_ganador)) == bet_value
            else SIN_PREMIO
        )

    if bet_type == "half":
        return (
            MULTIPLICADOR_CHANCE_SIMPLE
            if mitad_de(numero_ganador) == bet_value.lower()
            else SIN_PREMIO
        )

    return SIN_PREMIO
