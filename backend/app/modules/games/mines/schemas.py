from decimal import Decimal

from pydantic import BaseModel, Field

from app.modules.games.mines.paytable import (
    APUESTA_MAXIMA,
    APUESTA_MINIMA,
    CASILLAS,
    MAX_MINAS,
    MIN_MINAS,
)


class MinesEmpezar(BaseModel):
    bet_amount: Decimal = Field(..., ge=APUESTA_MINIMA, le=APUESTA_MAXIMA, decimal_places=2)
    minas: int = Field(3, ge=MIN_MINAS, le=MAX_MINAS)


class MinesDestapar(BaseModel):
    casilla: int = Field(..., ge=0, lt=CASILLAS)


class MinesRotarSeed(BaseModel):
    """El jugador elige el client seed de la semilla nueva."""

    client_seed: str | None = Field(None, max_length=64)


class MinesEstado(BaseModel):
    game_id: int
    bet_amount: Decimal
    minas: int
    destapadas: list[int]
    status: str  # ACTIVE, CASHED, BUSTED

    # Lo que paga cobrar ahora y lo que pagaría un acierto más. Con la grilla
    # cerrada, `premio_actual` es lo que se cobró (o cero).
    multiplicador: Decimal
    premio_actual: Decimal
    proximo_multiplicador: Decimal | None
    proximo_premio: Decimal | None

    payout: Decimal
    net_profit: Decimal

    # Sólo cuando la grilla cerró: dónde estaban las minas, para que el jugador
    # vea el tablero completo. Con la grilla abierta va en None.
    minas_en: list[int] | None = None

    server_seed_hash: str
    client_seed: str
    nonce: int
