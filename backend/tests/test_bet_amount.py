from decimal import Decimal

import pytest

from app.modules.games.shared.betting import parse_bet_amount


def test_monto_negativo_es_rechazado():
    """Regresión del exploit de Crash.

    place_bet hacía `user.balance -= Decimal(str(amount))` sin validar el monto,
    y la comprobación de saldo (`balance < amount`) siempre pasaba con negativos.
    Mandar {"action": "place_bet", "amount": -100000} acreditaba 100000 al saldo.
    """
    assert parse_bet_amount(-100000) is None


@pytest.mark.parametrize(
    "raw_amount",
    [
        -100000,
        -0.01,
        "-5",
        0,
        "0",
        0.009,  # queda por debajo del mínimo antes de redondear
        10000.01,
        "1e400",
        float("nan"),
        float("inf"),
        float("-inf"),
        "NaN",
        "Infinity",
        None,
        "",
        "abc",
        [1],
        {"amount": 1},
    ],
)
def test_rechaza_montos_invalidos(raw_amount):
    assert parse_bet_amount(raw_amount) is None


@pytest.mark.parametrize(
    "raw_amount, expected",
    [
        (10, "10.00"),
        (0.01, "0.01"),
        ("2.50", "2.50"),
        (2.999, "2.99"),  # trunca, nunca redondea a favor del jugador
        (10000, "10000.00"),
    ],
)
def test_acepta_y_normaliza_montos_validos(raw_amount, expected):
    assert parse_bet_amount(raw_amount) == Decimal(expected)


def test_devuelve_decimal_no_float():
    amount = parse_bet_amount(1.1)
    assert isinstance(amount, Decimal)
    assert amount == Decimal("1.10")
