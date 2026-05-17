import math
import random
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.games.infrastructure.models import Bet
from app.modules.games.plinko.schemas import PlinkoBetCreate, PlinkoResultResponse
from app.modules.users.infrastructure.models import User
from app.modules.wallet.infrastructure.models import Transaction

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


def simulate_plinko_drop(rows: int) -> dict:
    peg_r = PEG_RADIUS
    ball_r = BALL_RADIUS
    col_gap = get_col_gap(rows)
    min_x = get_slot_x(0, rows)
    max_x = get_slot_x(rows, rows)

    pegs = get_pegs(rows)

    # FIX 1: spread de entrada más amplio para que la pelota no siempre
    # nazca en el centro exacto. Antes era ±1.5 px, lo que favorecía
    # demasiado los slots centrales (y por simetría, los extremos en
    # tableros angostos).
    x = BOARD_CENTER_X + random.uniform(-7, 7)
    y = BALL_START_Y
    vx = random.uniform(-0.8, 0.8)
    vy = 1.0

    frames = [{"x": round(x, 2), "y": round(y, 2)}]

    max_steps = 1500
    for _ in range(max_steps):
        vy += 0.22
        vx += (BOARD_CENTER_X - x) * 0.00025
        x += vx
        y += vy
        vx *= 0.955

        if x < min_x:
            x = min_x
            vx = abs(vx) * 0.24
        elif x > max_x:
            x = max_x
            vx = -abs(vx) * 0.24

        for px, py in pegs:
            if abs(x - px) > 20 or abs(y - py) > 20:
                continue

            dx = x - px
            dy = y - py
            dist_sq = dx * dx + dy * dy
            min_dist = peg_r + ball_r

            if dist_sq < min_dist * min_dist:
                dist = math.sqrt(dist_sq)
                if dist == 0:
                    dist = 0.1
                nx = dx / dist
                ny = dy / dist

                overlap = min_dist - dist
                x += nx * overlap
                y += ny * overlap

                dot = vx * nx + vy * ny
                if dot < 0:
                    vx -= 1.34 * dot * nx
                    vy -= 1.34 * dot * ny

                # FIX 2: ruido lateral más alto (±0.8 vs ±0.4 original).
                # Con poco ruido la pelota tendía a seguir trayectorias
                # casi deterministas que terminaban en los extremos.
                vx += random.uniform(-0.38, 0.38)
                vx = max(-2.7, min(2.7, vx))
                vy = max(0.65, abs(vy) * 0.42 + 0.38)

        frames.append({"x": round(x, 2), "y": round(y, 2)})

        if y >= BOARD_FLOOR_Y - ball_r:
            break

    # FIX 3: usar el mismo col_gap unificado para calcular el slot final.
    # Antes se usaba COL_GAP=46 fijo aquí pero get_col_gap() para los slots
    # del board, lo que producía un desajuste entre donde caía la pelota
    # visualmente y el slot que se registraba (y por ende el multiplicador).
    actual_slot = round((x - BOARD_CENTER_X) / col_gap + rows / 2.0)
    actual_slot = max(0, min(rows, int(actual_slot)))

    return {
        "path": [],
        "slot_index": actual_slot,
        "board": build_board_map(rows),
        "visual_path": frames,
    }


def simulate_plinko_drop_balanced_path(rows: int) -> dict:
    col_gap = get_col_gap(rows)
    frames = [{"x": round(BOARD_CENTER_X + random.uniform(-4, 4), 2), "y": BALL_START_Y}]
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
        direction = random.choice(["L", "R"])
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
        append_arc(exit_x + side * random.uniform(0.4, 1.2), peg_y + 18, 6, sag=1.5)

    slot_index = rights
    append_arc(get_slot_x(slot_index, rows), BOARD_FLOOR_Y - BALL_RADIUS, 14)

    return {
        "path": path,
        "slot_index": slot_index,
        "board": build_board_map(rows),
        "visual_path": frames,
    }


async def play_plinko_service(
    db: AsyncSession,
    user_id: int,
    bet_data: PlinkoBetCreate,
) -> PlinkoResultResponse:
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    if user.balance < bet_data.bet_amount:
        raise HTTPException(status_code=400, detail="Saldo insuficiente")

    user.balance -= bet_data.bet_amount

    drop = simulate_plinko_drop(bet_data.rows)
    path = drop["path"]
    slot_index = drop["slot_index"]
    multipliers = build_multipliers(bet_data.rows, bet_data.risk)
    multiplier = multipliers[slot_index]
    total_payout = _round_money(bet_data.bet_amount * multiplier)
    visual_path = drop["visual_path"]

    if total_payout > 0:
        user.balance += total_payout

    result_data = {
        "risk": bet_data.risk,
        "rows": bet_data.rows,
        "board": drop["board"],
        "path": path,
        "visual_path": visual_path,
        "slot_index": slot_index,
        "multiplier": str(multiplier),
        "multipliers": [str(item) for item in multipliers],
    }

    bet_record = Bet(
        user_id=user_id,
        game_id="plinko",
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
        game_id="plinko",
        bet_amount=bet_data.bet_amount,
        total_payout=total_payout,
        net_profit=total_payout - bet_data.bet_amount,
        result_data=result_data,
    )
