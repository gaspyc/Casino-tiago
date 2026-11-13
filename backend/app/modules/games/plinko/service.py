import math
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.games.infrastructure.models import Bet, GameSeed
from app.modules.games.plinko.fairness import derivar_camino, slot_desde_camino
from app.modules.games.plinko.schemas import PlinkoBetCreate, PlinkoResultResponse
from app.modules.games.shared import compromiso, rng
from app.modules.wallet.application.balance import credit, debit
from app.modules.wallet.infrastructure.models import Transaction

GAME_ID = "plinko"

RISK_CONFIG = {
    "low": {"alpha": 0.28, "floor": 0.45, "cap": 16.0},
    "medium": {"alpha": 0.42, "floor": 0.25, "cap": 120.0},
    "high": {"alpha": 0.62, "floor": 0.0, "cap": 1000.0},
}
TARGET_RTP = 0.96
CENT = Decimal("0.01")
BOARD_CENTER_X = 450
BALL_START_Y = 24
PEG_START_Y = 58
ROW_GAP = 35
BOARD_WIDTH = 620
BOARD_FLOOR_Y = 590
BALL_RADIUS = 9
PEG_RADIUS = 6
GRAVITY = 520.0
FRAME_MS = 32.0

# COL_GAP ya no es una constante global fija —
# se calcula dinámicamente según el número de filas
# para que pines y slots compartan el mismo espaciado.


def _round_money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _round_multiplier(value: float) -> Decimal:
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


def build_multipliers(rows: int, risk: str) -> list[Decimal]:
    config = RISK_CONFIG[risk]
    probabilities = [math.comb(rows, slot) / (2**rows) for slot in range(rows + 1)]

    raw = []
    for probability in probabilities:
        multiplier = config["floor"] + (1 / probability) ** config["alpha"] * 0.12
        raw.append(min(multiplier, config["cap"]))

    expected_value = sum(prob * multiplier for prob, multiplier in zip(probabilities, raw))
    scale = TARGET_RTP / expected_value
    return [_round_multiplier(multiplier * scale) for multiplier in raw]


def get_col_gap(rows: int) -> float:
    """
    Gap unificado para pines Y slots.
    Antes había dos valores distintos (COL_GAP=46 fijo para pines,
    BOARD_WIDTH/(rows+1) para slots), lo que hacía que la posición
    física de la pelota no mapeara correctamente al índice de slot.
    Usar +2 en el denominador deja margen en los bordes y evita que
    la pelota caiga fuera del área de slots.
    """
    return BOARD_WIDTH / (rows + 2)


def get_slot_x(slot_index: int, rows: int) -> float:
    return BOARD_CENTER_X + (slot_index - rows / 2) * get_col_gap(rows)


def get_pegs(rows: int) -> list[tuple[float, float]]:
    """Usa get_col_gap() en lugar del COL_GAP fijo anterior."""
    col_gap = get_col_gap(rows)
    pegs = []
    for row in range(rows):
        for index in range(row + 1):
            pegs.append(
                (
                    BOARD_CENTER_X + (index - row / 2.0) * col_gap,
                    PEG_START_Y + row * ROW_GAP,
                )
            )
    return pegs


def build_board_map(rows: int) -> dict:
    col_gap = get_col_gap(rows)
    return {
        "center_x": BOARD_CENTER_X,
        "start_y": BALL_START_Y,
        "floor_y": BOARD_FLOOR_Y,
        "row_gap": ROW_GAP,
        "col_gap": round(col_gap, 2),
        "ball_radius": BALL_RADIUS,
        "peg_radius": PEG_RADIUS,
        "pegs": [
            {"x": round(x, 2), "y": round(y, 2), "r": PEG_RADIUS}
            for x, y in get_pegs(rows)
        ],
        "slots": [
            {"index": index, "x": round(get_slot_x(index, rows), 2)}
            for index in range(rows + 1)
        ],
    }


# La simulación física que decidía el slot se eliminó: su distribución no era
# binomial (el clamp de los bordes acumulaba masa en los slots de mayor
# multiplicador) y el RTP real llegaba al 177% en riesgo alto. Ahora el camino
# sale del seed y la física quedó solamente para la animación.
def construir_tiro(rows: int, camino: list) -> dict:
    """Arma la animación para un camino ya decidido por el seed."""
    if len(camino) != rows:
        raise ValueError("El camino no coincide con la cantidad de filas")

    col_gap = get_col_gap(rows)
    frames = [{"x": round(BOARD_CENTER_X + rng.uniform(-4, 4), 2), "y": BALL_START_Y}]
    path: list[str] = []
    rights = 0

    def append_arc(target_x: float, target_y: float, steps: int, sag: float = 0.0) -> None:
        start = frames[-1]
        for step in range(1, steps + 1):
            t = step / steps
            gravity_curve = t * t
            x = start["x"] + (target_x - start["x"]) * t
            y = start["y"] + (target_y - start["y"]) * gravity_curve - sag * math.sin(math.pi * t)
            frames.append({"x": round(x, 2), "y": round(y, 2)})

    for row in range(rows):
        direction = camino[row]
        path.append(direction)

        peg_x = BOARD_CENTER_X + (rights - row / 2.0) * col_gap
        peg_y = PEG_START_Y + row * ROW_GAP
        side = 1 if direction == "R" else -1
        contact_x = peg_x - side * (BALL_RADIUS + PEG_RADIUS - 1.5)
        contact_y = peg_y - 2

        append_arc(contact_x, contact_y, 7, sag=3.0)

        for step in range(1, 4):
            t = step / 3
            frames.append(
                {
                    "x": round(contact_x + side * 4.5 * t, 2),
                    "y": round(contact_y + 3.5 * t, 2),
                }
            )

        if direction == "R":
            rights += 1

        exit_x = BOARD_CENTER_X + (rights - (row + 1) / 2.0) * col_gap
        append_arc(exit_x + side * rng.uniform(0.4, 1.2), peg_y + 18, 6, sag=1.5)

    slot_index = rights
    append_arc(get_slot_x(slot_index, rows), BOARD_FLOOR_Y - BALL_RADIUS, 14)

    return {
        "path": path,
        "slot_index": slot_index,
        "board": build_board_map(rows),
        "visual_path": frames,
    }


async def obtener_semilla_activa(db: AsyncSession, user_id: int) -> GameSeed:
    """La semilla vigente del jugador en plinko. El ciclo vive en shared."""
    return await compromiso.obtener_semilla_activa(db, user_id, GAME_ID)


async def rotar_semilla(
    db: AsyncSession,
    user_id: int,
    client_seed: str = None,
) -> dict:
    """Revela la semilla vigente y deja una nueva.

    Con el seed revelado el jugador rehace el camino de todas las bolas que tiró
    con esa semilla, nonce por nonce.
    """
    return await compromiso.rotar_semilla(db, user_id, GAME_ID, client_seed)


describir_semilla = compromiso.describir_semilla


async def play_plinko_service(
    db: AsyncSession,
    user_id: int,
    bet_data: PlinkoBetCreate,
) -> PlinkoResultResponse:
    semilla = await obtener_semilla_activa(db, user_id)

    if not await debit(db, user_id, bet_data.bet_amount):
        raise HTTPException(status_code=400, detail="Saldo insuficiente")

    # El nonce se incrementa en la base: dos bolas simultáneas no pueden caer en
    # el mismo, que daría el mismo camino y rompería la verificación.
    nonce = await compromiso.siguiente_nonce(db, semilla)

    camino = derivar_camino(
        semilla.server_seed, semilla.client_seed, nonce, bet_data.rows
    )
    slot_index = slot_desde_camino(camino)
    tiro = construir_tiro(bet_data.rows, camino)

    multipliers = build_multipliers(bet_data.rows, bet_data.risk)
    multiplier = multipliers[slot_index]
    total_payout = _round_money(bet_data.bet_amount * multiplier)

    if total_payout > 0:
        await credit(db, user_id, total_payout)

    result_data = {
        "risk": bet_data.risk,
        "rows": bet_data.rows,
        "board": tiro["board"],
        "path": tiro["path"],
        "visual_path": tiro["visual_path"],
        "slot_index": slot_index,
        "multiplier": str(multiplier),
        "multipliers": [str(item) for item in multipliers],
        # Para verificar: el hash ya estaba publicado antes de esta jugada.
        "server_seed_hash": semilla.server_seed_hash,
        "client_seed": semilla.client_seed,
        "nonce": nonce,
    }

    bet_record = Bet(
        user_id=user_id,
        game_id=GAME_ID,
        bet_amount=bet_data.bet_amount,
        payout=total_payout,
        result_data=result_data,
    )
    db.add(bet_record)

    db.add(
        Transaction(
            user_id=user_id,
            amount=bet_data.bet_amount,
            transaction_type="BET",
            description="Plinko",
        )
    )

    if total_payout > 0:
        db.add(
            Transaction(
                user_id=user_id,
                amount=total_payout,
                transaction_type="PAYOUT",
                description="Plinko",
            )
        )

    await db.commit()

    return PlinkoResultResponse(
        game_id=GAME_ID,
        bet_amount=bet_data.bet_amount,
        total_payout=total_payout,
        net_profit=total_payout - bet_data.bet_amount,
        result_data=result_data,
    )
