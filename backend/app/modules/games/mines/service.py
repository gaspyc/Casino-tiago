"""Mines: una grilla de 25 con minas escondidas y cobro cuando quieras.

Las tres reglas que hacen que la plata cierre:

1. La apuesta se debita al empezar y sólo vuelve si el jugador cobra. Tocar una
   mina no debita nada extra: ya estaba cobrado.
2. Las minas no se guardan, se derivan del seed. Así no hay ningún camino por
   el que puedan salir en una respuesta antes de tiempo.
3. Una sola grilla abierta por jugador, garantizado por un índice único parcial
   en la base. Dos grillas abiertas serían dos apuestas debitadas y una sola
   pantalla para cobrarlas.
"""

from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.games.infrastructure.models import Bet, MinesGame
from app.modules.games.mines.fairness import orden_del_tablero
from app.modules.games.mines.paytable import (
    CASILLAS,
    multiplicador,
    premio,
)
from app.modules.games.mines.schemas import MinesEstado
from app.modules.games.shared import compromiso
from app.modules.wallet.application.balance import credit, debit
from app.modules.wallet.infrastructure.models import Transaction

GAME_ID = "mines"

ACTIVA = "ACTIVE"
COBRADA = "CASHED"
EXPLOTADA = "BUSTED"


# ------------------------------ el tablero ------------------------------

def _minas_de(fila: MinesGame, server_seed: str) -> set:
    """Dónde están las minas de esta grilla. Derivadas, nunca guardadas."""
    orden = orden_del_tablero(server_seed, fila.client_seed, fila.nonce)
    return set(orden[: fila.minas])


async def _server_seed(db: AsyncSession, fila: MinesGame) -> str:
    semilla = await compromiso.semilla_por_id(db, fila.seed_id)
    if semilla is None:
        raise HTTPException(status_code=500, detail="Falta la semilla de la grilla")

    return semilla.server_seed


def _estado(fila: MinesGame, minas_en: set = None) -> MinesEstado:
    destapadas = list(fila.destapadas)
    aciertos = len(destapadas)
    apuesta = Decimal(fila.bet_amount)

    abierta = fila.status == ACTIVA
    quedan = CASILLAS - fila.minas - aciertos

    return MinesEstado(
        game_id=fila.id,
        bet_amount=apuesta,
        minas=fila.minas,
        destapadas=destapadas,
        status=fila.status,
        multiplicador=multiplicador(fila.minas, aciertos),
        premio_actual=(
            premio(apuesta, fila.minas, aciertos) if abierta else Decimal(fila.payout)
        ),
        proximo_multiplicador=(
            multiplicador(fila.minas, aciertos + 1) if abierta and quedan else None
        ),
        proximo_premio=(
            premio(apuesta, fila.minas, aciertos + 1) if abierta and quedan else None
        ),
        payout=Decimal(fila.payout),
        net_profit=Decimal(fila.payout) - apuesta,
        # El tablero completo recién cuando la grilla cerró.
        minas_en=sorted(minas_en) if minas_en is not None and not abierta else None,
        server_seed_hash=fila.server_seed_hash,
        client_seed=fila.client_seed,
        nonce=fila.nonce,
    )


# ------------------------------ jugar ------------------------------

async def empezar(
    db: AsyncSession,
    user_id: int,
    apuesta: Decimal,
    minas: int,
) -> MinesEstado:
    if await _grilla_abierta(db, user_id) is not None:
        raise HTTPException(
            status_code=409, detail="Ya tenés una grilla abierta, terminala primero"
        )

    semilla = await compromiso.obtener_semilla_activa(db, user_id, GAME_ID)

    if not await debit(db, user_id, apuesta):
        raise HTTPException(status_code=400, detail="Saldo insuficiente")

    db.add(
        Transaction(
            user_id=user_id,
            amount=apuesta,
            transaction_type="BET",
            description="Mines",
        )
    )

    # El nonce se reserva en la base: dos grillas simultáneas no pueden caer en
    # el mismo, que daría el mismo tablero.
    nonce = await compromiso.siguiente_nonce(db, semilla)

    fila = MinesGame(
        user_id=user_id,
        bet_amount=apuesta,
        minas=minas,
        destapadas=[],
        status=ACTIVA,
        payout=Decimal("0.00"),
        seed_id=semilla.id,
        nonce=nonce,
        server_seed_hash=semilla.server_seed_hash,
        client_seed=semilla.client_seed,
    )
    db.add(fila)

    try:
        await db.commit()
    except IntegrityError:
        # El índice único parcial atajó dos "empezar" simultáneos. La apuesta
        # no se debita porque la transacción entera se va para atrás.
        await db.rollback()
        raise HTTPException(
            status_code=409, detail="Ya tenés una grilla abierta, terminala primero"
        )

    await db.refresh(fila)
    return _estado(fila)


async def destapar(
    db: AsyncSession,
    user_id: int,
    casilla: int,
) -> MinesEstado:
    fila = await _grilla_abierta(db, user_id)
    if fila is None:
        raise HTTPException(status_code=404, detail="No tenés ninguna grilla abierta")

    if casilla in fila.destapadas:
        raise HTTPException(status_code=400, detail="Esa casilla ya está destapada")

    minas_en = _minas_de(fila, await _server_seed(db, fila))

    if casilla in minas_en:
        # Perdió: la apuesta ya estaba debitada, no se cobra nada más.
        fila.status = EXPLOTADA
        fila.payout = Decimal("0.00")
        fila.destapadas = list(fila.destapadas) + [casilla]
        await _registrar_apuesta(db, fila)
        await db.commit()
        await db.refresh(fila)
        return _estado(fila, minas_en)

    fila.destapadas = list(fila.destapadas) + [casilla]

    # Si no quedan casillas limpias, la grilla se cobra sola: no tiene sentido
    # pedirle al jugador que apriete cobrar cuando no hay nada más que destapar.
    if len(fila.destapadas) == CASILLAS - fila.minas:
        await db.flush()
        return await _liquidar(db, user_id, fila, minas_en)

    await db.commit()
    await db.refresh(fila)
    return _estado(fila)


async def cobrar(db: AsyncSession, user_id: int) -> MinesEstado:
    fila = await _grilla_abierta(db, user_id)
    if fila is None:
        raise HTTPException(status_code=404, detail="No tenés ninguna grilla abierta")

    if not fila.destapadas:
        # Cobrar sin destapar nada devolvería la apuesta intacta: no es una
        # jugada, es una forma de mover saldo sin arriesgar.
        raise HTTPException(
            status_code=400, detail="Destapá al menos una casilla antes de cobrar"
        )

    minas_en = _minas_de(fila, await _server_seed(db, fila))
    return await _liquidar(db, user_id, fila, minas_en)


async def _liquidar(
    db: AsyncSession,
    user_id: int,
    fila: MinesGame,
    minas_en: set,
) -> MinesEstado:
    total = premio(Decimal(fila.bet_amount), fila.minas, len(fila.destapadas))

    fila.status = COBRADA
    fila.payout = total

    await credit(db, user_id, total)
    db.add(
        Transaction(
            user_id=user_id,
            amount=total,
            transaction_type="PAYOUT",
            description="Mines",
        )
    )
    await _registrar_apuesta(db, fila)

    await db.commit()
    await db.refresh(fila)
    return _estado(fila, minas_en)


async def _registrar_apuesta(db: AsyncSession, fila: MinesGame) -> None:
    db.add(
        Bet(
            user_id=fila.user_id,
            game_id=GAME_ID,
            bet_amount=Decimal(fila.bet_amount),
            payout=Decimal(fila.payout),
            result_data={
                "minas": fila.minas,
                "destapadas": list(fila.destapadas),
                "status": fila.status,
                "server_seed_hash": fila.server_seed_hash,
                "client_seed": fila.client_seed,
                "nonce": fila.nonce,
            },
        )
    )


# ------------------------------ retomar ------------------------------

async def _grilla_abierta(db: AsyncSession, user_id: int) -> MinesGame:
    return await db.scalar(
        select(MinesGame)
        .where(MinesGame.user_id == user_id, MinesGame.status == ACTIVA)
        .limit(1)
    )


async def ver_activa(db: AsyncSession, user_id: int) -> MinesEstado:
    """La grilla sin terminar, para retomarla al volver.

    Igual que en el blackjack: la apuesta se debita al empezar, así que una
    grilla que no se puede retomar es plata perdida.
    """
    fila = await _grilla_abierta(db, user_id)
    return None if fila is None else _estado(fila)


# ------------------------------ provably fair ------------------------------

async def obtener_semilla_mines(db: AsyncSession, user_id: int):
    return await compromiso.obtener_semilla_activa(db, user_id, GAME_ID)


async def rotar_semilla_mines(
    db: AsyncSession,
    user_id: int,
    client_seed: str = None,
) -> dict:
    """Revela la semilla vigente y deja una nueva.

    Con una grilla abierta no se puede, por el mismo motivo que en el
    blackjack: el server seed es el mapa de las minas.
    """
    if await _grilla_abierta(db, user_id) is not None:
        raise HTTPException(
            status_code=409,
            detail="Terminá la grilla abierta antes de revelar la semilla",
        )

    return await compromiso.rotar_semilla(db, user_id, GAME_ID, client_seed)
