from fastapi import WebSocket
from typing import Dict, List
import json

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, table_id: int):
        await websocket.accept()
        if table_id not in self.active_connections:
            self.active_connections[table_id] = []
        self.active_connections[table_id].append(websocket)

    def disconnect(self, websocket: WebSocket, table_id: int):
        if table_id in self.active_connections:
            if websocket in self.active_connections[table_id]:
                self.active_connections[table_id].remove(websocket)
            if not self.active_connections[table_id]:
                del self.active_connections[table_id]

    async def broadcast(self, message: dict, table_id: int):
        if table_id in self.active_connections:
            msg_str = json.dumps(message)
            for connection in self.active_connections[table_id]:
                try:
                    await connection.send_text(msg_str)
                except Exception:
                    pass

manager = ConnectionManager()
