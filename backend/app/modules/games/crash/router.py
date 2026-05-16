import json

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.modules.games.crash.service import crash_manager
from app.modules.users.infrastructure.models import User
from app.shared.database import get_db
from app.shared.security import verify_access_token

router = APIRouter(prefix="/crash", tags=["Crash Game"])


@router.websocket("/ws")
async def websocket_crash_endpoint(
    websocket: WebSocket,
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    payload = verify_access_token(token)
    if not payload:
        await websocket.close(code=1008)
        return

    username = payload.get("sub")
    if not username:
        await websocket.close(code=1008)
        return

    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if not user:
        await websocket.close(code=1008)
        return

    user_id = user.id

    await crash_manager.connection_manager.connect(websocket)

    state = {
        "status": crash_manager.status,
        "multiplier": crash_manager.multiplier,
        "timer": crash_manager.timer,
        "bets": list(crash_manager.bets.values()),
    }
    await websocket.send_json({"type": "state", "data": state})

    try:
        while True:
            data = await websocket.receive_text()
            action_data = json.loads(data)
            action = action_data.get("action")

            if action == "place_bet":
                amount = float(action_data.get("amount", 0))
                await crash_manager.place_bet(user_id, username, amount)

            elif action == "cash_out":
                await crash_manager.cash_out(user_id)

    except WebSocketDisconnect:
        crash_manager.connection_manager.disconnect(websocket)
