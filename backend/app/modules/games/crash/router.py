import json

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.modules.games.crash.service import crash_manager
from app.modules.games.infrastructure.models import CrashGameSession
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

    await websocket.send_json({"type": "state", "data": await crash_manager.current_state()})

    try:
        while True:
            data = await websocket.receive_text()

            try:
                action_data = json.loads(data)
            except json.JSONDecodeError:
                continue

            if not isinstance(action_data, dict):
                continue

            action = action_data.get("action")

            if action == "place_bet":
                # El monto se pasa sin convertir: lo valida place_bet.
                await crash_manager.place_bet(user_id, username, action_data.get("amount"))

            elif action == "cash_out":
                await crash_manager.cash_out(user_id)

    except WebSocketDisconnect:
        crash_manager.connection_manager.disconnect(websocket)


@router.get("/history")
async def crash_history(db: AsyncSession = Depends(get_db)):
    """Rondas terminadas con sus seeds, para verificar los resultados.

    No lleva auth a propósito: el sentido de publicar los seeds es que cualquiera
    pueda rehacer la cuenta. Verificar acá no probaría nada, la verificación se
    hace por afuera con la fórmula documentada en fairness.py.
    """
    stmt = (
        select(CrashGameSession)
        .where(CrashGameSession.status == "CRASHED")
        .order_by(CrashGameSession.id.desc())
        .limit(20)
    )
    result = await db.execute(stmt)

    return [
        {
            "id": sesion.id,
            "crash_point": float(sesion.crash_point),
            "server_seed": sesion.server_seed,
            "server_seed_hash": sesion.server_seed_hash,
            "client_seed": sesion.client_seed,
            "nonce": sesion.nonce,
            "created_at": sesion.created_at,
        }
        for sesion in result.scalars().all()
    ]
