import json

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.modules.games.infrastructure.models import PokerTable
from app.modules.games.poker.multiplayer_service import get_poker_state, process_ws_poker_action
from app.modules.games.shared.schemas import TableResponse
from app.modules.users.infrastructure.models import User
from app.shared.database import get_db
from app.shared.security import verify_access_token
from app.shared.websockets import manager

router = APIRouter(prefix="/poker-mp", tags=["Poker Multiplayer"])


@router.get("/tables", response_model=list[TableResponse])
async def list_tables(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(PokerTable))
    tables = result.scalars().all()

    if not tables:
        default_table = PokerTable(name="Mesa Texas Hold'em", deck=[], community_cards=[])
        db.add(default_table)
        await db.commit()
        await db.refresh(default_table)
        tables = [default_table]

    return [
        TableResponse(
            id=t.id,
            name=t.name,
            status=t.status,
            player_count=len(t.players_data) if isinstance(t.players_data, list) else 0,
        )
        for t in tables
    ]


@router.websocket("/ws/{table_id}")
async def websocket_poker_endpoint(
    websocket: WebSocket,
    table_id: int,
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

    poker_room_id = f"poker_{table_id}"
    await manager.connect(websocket, poker_room_id)

    state = await get_poker_state(db, table_id)
    if state:
        await websocket.send_text(json.dumps({"type": "state_update", "data": state}))

    try:
        while True:
            data = await websocket.receive_text()
            action_data = json.loads(data)

            new_state = await process_ws_poker_action(db, table_id, user_id, action_data)

            if new_state:
                await manager.broadcast({"type": "state_update", "data": new_state}, poker_room_id)

    except WebSocketDisconnect:
        manager.disconnect(websocket, poker_room_id)
        new_state = await process_ws_poker_action(db, table_id, user_id, {"action": "leave"})
        if new_state:
            await manager.broadcast({"type": "state_update", "data": new_state}, poker_room_id)
