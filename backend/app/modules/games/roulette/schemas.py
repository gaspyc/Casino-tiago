from decimal import Decimal
from typing import FrozenSet, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

MIN_NUMBER = 0
MAX_NUMBER = 36


def _build_valid_splits() -> FrozenSet[FrozenSet[int]]:
    """Pares de números contiguos en el paño (incluye los splits del cero)."""
    splits = {frozenset({0, 1}), frozenset({0, 2}), frozenset({0, 3})}
    for number in range(1, MAX_NUMBER + 1):
        if number % 3 != 0:  # vecino dentro de la misma columna de tres
            splits.add(frozenset({number, number + 1}))
        if number + 3 <= MAX_NUMBER:  # vecino en la columna siguiente
            splits.add(frozenset({number, number + 3}))
    return frozenset(splits)


def _build_valid_corners() -> FrozenSet[FrozenSet[int]]:
    """Cuadros de cuatro números, más el 'first four' (0-1-2-3), que paga igual."""
    corners = {frozenset({0, 1, 2, 3})}
    for number in range(1, MAX_NUMBER - 3):
        if number % 3 != 0:
            corners.add(frozenset({number, number + 1, number + 3, number + 4}))
    return frozenset(corners)


VALID_SPLITS = _build_valid_splits()
VALID_CORNERS = _build_valid_corners()


def _parse_number(raw: str) -> Optional[int]:
    try:
        number = int(raw)
    except (TypeError, ValueError):
        return None
    return number if MIN_NUMBER <= number <= MAX_NUMBER else None


def _parse_number_set(raw: str, expected: int) -> Optional[FrozenSet[int]]:
    parts = [part.strip() for part in raw.split(",")]
    if len(parts) != expected:
        return None

    numbers = [_parse_number(part) for part in parts]
    if any(number is None for number in numbers):
        return None

    combination = frozenset(numbers)
    return combination if len(combination) == expected else None


def _format_numbers(numbers: FrozenSet[int]) -> str:
    return ",".join(str(number) for number in sorted(numbers))


class RouletteBetItem(BaseModel):
    bet_amount: Decimal = Field(..., gt=0, decimal_places=2)
    bet_type: Literal["number", "color", "parity", "split", "corner"]
    bet_value: str

    @model_validator(mode="after")
    def _validate_bet_value(self) -> "RouletteBetItem":
        """Valida bet_value contra el paño y lo deja en forma canónica.

        Sin esto, un split o un corner aceptaban cualquier lista de números: se
        podía apostar a los 37 números y cobrar 18x garantizado.
        """
        raw = self.bet_value.strip()

        if self.bet_type == "number":
            number = _parse_number(raw)
            if number is None:
                raise ValueError("bet_value debe ser un número entre 0 y 36")
            self.bet_value = str(number)

        elif self.bet_type == "color":
            color = raw.lower()
            if color not in {"red", "black"}:
                raise ValueError("bet_value debe ser 'red' o 'black'")
            self.bet_value = color

        elif self.bet_type == "parity":
            parity = raw.lower()
            if parity not in {"even", "odd"}:
                raise ValueError("bet_value debe ser 'even' u 'odd'")
            self.bet_value = parity

        elif self.bet_type == "split":
            numbers = _parse_number_set(raw, 2)
            if numbers is None or numbers not in VALID_SPLITS:
                raise ValueError("bet_value debe ser un split de dos números contiguos")
            self.bet_value = _format_numbers(numbers)

        elif self.bet_type == "corner":
            numbers = _parse_number_set(raw, 4)
            if numbers is None or numbers not in VALID_CORNERS:
                raise ValueError("bet_value debe ser un corner de cuatro números contiguos")
            self.bet_value = _format_numbers(numbers)

        return self


class RouletteBetCreate(BaseModel):
    bets: List[RouletteBetItem] = Field(..., min_length=1)


class BetResultDetail(BaseModel):
    bet_type: str
    bet_value: str
    bet_amount: Decimal
    payout: Decimal
    win: bool


class GameResultResponse(BaseModel):
    game_id: str
    total_bet_amount: Decimal
    total_payout: Decimal
    net_profit: Decimal
    result_data: dict
    bet_details: List[BetResultDetail]
