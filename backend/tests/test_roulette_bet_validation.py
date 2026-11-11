import pytest
from pydantic import ValidationError

from app.modules.games.roulette.schemas import RouletteBetItem

TODOS_LOS_NUMEROS = ",".join(str(number) for number in range(37))


def _bet(bet_type: str, bet_value: str) -> RouletteBetItem:
    return RouletteBetItem(bet_amount="10.00", bet_type=bet_type, bet_value=bet_value)


def test_split_con_todos_los_numeros_es_rechazado():
    """Regresión del exploit de ruleta.

    El servicio sólo hacía `str(winning_number) in bet_value.split(",")`, así que
    un split con los 37 números cobraba 18x en todos los giros.
    """
    with pytest.raises(ValidationError):
        _bet("split", TODOS_LOS_NUMEROS)


def test_corner_con_todos_los_numeros_es_rechazado():
    """Misma variante, cobrando 9x garantizado."""
    with pytest.raises(ValidationError):
        _bet("corner", TODOS_LOS_NUMEROS)


@pytest.mark.parametrize("bet_value", ["1,2", "2,3", "1,4", "33,36", "34,35", "0,1", "0,3"])
def test_splits_validos(bet_value):
    assert _bet("split", bet_value).bet_value


@pytest.mark.parametrize(
    "bet_value",
    ["1,3", "3,4", "1,5", "1,7", "36,37", "1", "1,2,3", "1,1", "1,-2", "a,b", ""],
)
def test_splits_invalidos(bet_value):
    with pytest.raises(ValidationError):
        _bet("split", bet_value)


@pytest.mark.parametrize("bet_value", ["1,2,4,5", "2,3,5,6", "31,32,34,35", "32,33,35,36", "0,1,2,3"])
def test_corners_validos(bet_value):
    assert _bet("corner", bet_value).bet_value


@pytest.mark.parametrize(
    "bet_value",
    ["1,2,3,4", "3,4,6,7", "1,2,4,6", "34,35,37,38", "1,2,4", "1,2,4,5,7", "1,1,4,5"],
)
def test_corners_invalidos(bet_value):
    with pytest.raises(ValidationError):
        _bet("corner", bet_value)


@pytest.mark.parametrize("bet_value", ["37", "-1", "1.5", "07x", ""])
def test_numeros_fuera_del_pano_son_rechazados(bet_value):
    with pytest.raises(ValidationError):
        _bet("number", bet_value)


@pytest.mark.parametrize(
    "bet_type, bet_value",
    [
        ("color", "green"),  # pagaba 2x sobre el cero: RTP 5.4%
        ("parity", "none"),  # idem
        ("color", "azul"),
        ("parity", "par"),
    ],
)
def test_apuestas_que_no_existen_en_el_pano(bet_type, bet_value):
    with pytest.raises(ValidationError):
        _bet(bet_type, bet_value)


@pytest.mark.parametrize(
    "bet_type, bet_value, expected",
    [
        ("number", " 07 ", "7"),
        ("color", "RED", "red"),
        ("parity", "Even", "even"),
        ("split", "4, 1", "1,4"),
        ("corner", "5,4,2,1", "1,2,4,5"),
    ],
)
def test_normaliza_el_valor_de_la_apuesta(bet_type, bet_value, expected):
    assert _bet(bet_type, bet_value).bet_value == expected


# ------------------- docenas, columnas y mitades -------------------
# El paño las ofrecía desde el principio y el servicio las pagaba bien, pero el
# schema las rechazaba con 422: cualquier giro que las incluyera fallaba entero.

TIPOS_QUE_MANDA_EL_PANO = [
    ("number", "17"),
    ("color", "red"),
    ("parity", "even"),
    ("split", "1,2"),
    ("corner", "1,2,4,5"),
    ("dozen", "1"),
    ("column", "2"),
    ("half", "low"),
]


@pytest.mark.parametrize("bet_type, bet_value", TIPOS_QUE_MANDA_EL_PANO)
def test_el_schema_acepta_todo_lo_que_ofrece_el_pano(bet_type, bet_value):
    assert _bet(bet_type, bet_value).bet_value


@pytest.mark.parametrize("bet_type", ["dozen", "column"])
@pytest.mark.parametrize("bet_value", ["0", "4", "-1", "1,2", "primera", ""])
def test_docenas_y_columnas_invalidas(bet_type, bet_value):
    with pytest.raises(ValidationError):
        _bet(bet_type, bet_value)


@pytest.mark.parametrize("bet_value", ["baja", "1", "low,high", ""])
def test_mitades_invalidas(bet_value):
    with pytest.raises(ValidationError):
        _bet("half", bet_value)


@pytest.mark.parametrize(
    "bet_type, bet_value, expected",
    [
        ("dozen", " 2 ", "2"),
        ("column", " 3 ", "3"),
        ("half", "HIGH", "high"),
    ],
)
def test_normaliza_las_apuestas_externas(bet_type, bet_value, expected):
    assert _bet(bet_type, bet_value).bet_value == expected
