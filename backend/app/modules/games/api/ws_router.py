import json
from decimal import Decimal
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.shared.database import get_db
from app.shared.websockets import manager
from app.shared.security import verify_access_token
from app.modules.users.infrastructure.models import User
from app.modules.games.infrastructure.models import BlackjackTable
from app.modules.games.domain.multiplayer_entities import TableResponse
from app.modules.games.application.ws_blackjack_service import process_ws_action, get_table_state

router = APIRouter(prefix="/games/blackjack-mp", tags=["Blackjack Multiplayer"])

@router.get("/tables", response_model=list[TableResponse])
async def list_tables(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(BlackjackTable))
    tables = result.scalars().all()
    
    # Si no hay mesas, creamos una por defecto
    if not tables:
        default_table = BlackjackTable(name="Mesa Principal VIP", deck=[], dealer_hand=[])
        db.add(default_table)
        await db.commit()
        await db.refresh(default_table)
        tables = [default_table]
        
    return [
        TableResponse(
            id=t.id, 
            name=t.name, 
            status=t.status, 
            player_count=len(t.players_data) if isinstance(t.players_data, list) else 0
        ) for t in tables
    ]

@router.websocket("/ws/{table_id}")
async def websocket_endpoint(websocket: WebSocket, table_id: int, token: str = Query(...), db: AsyncSession = Depends(get_db)):
    payload = verify_access_token(token)
    if not payload:
        await websocket.close(code=1008)
        return
        
    username = payload.get("sub")
    if not username:
        await websocket.close(code=1008)
        return
        
    # Verify user exists
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if not user:
        await websocket.close(code=1008)
        return
        
    user_id = user.id

    await manager.connect(websocket, table_id)
    
    # Enviar estado actual de la mesa al conectar
    state = await get_table_state(db, table_id)
    if state:
        await websocket.send_text(json.dumps({"type": "state_update", "data": state}))
    
    try:
        while True:
            data = await websocket.receive_text()
            action_data = json.loads(data)
            
            # Procesar la acción (join, bet, hit, stand)
            new_state = await process_ws_action(db, table_id, user_id, action_data)
            
            # Broadcast the new state to all connected clients
            if new_state:
                await manager.broadcast({"type": "state_update", "data": new_state}, table_id)
                
    except WebSocketDisconnect:
        manager.disconnect(websocket, table_id)
        # Opcionalmente, manejar desconexión del jugador en la DB si está "sentado"
        pass
