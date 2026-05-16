import asyncio
import random
import math
from typing import Dict, List
from fastapi import WebSocket
from app.shared.database import AsyncSessionLocal
from app.modules.games.infrastructure.models import CrashGameSession, CrashBet
from app.modules.users.infrastructure.models import User
from app.modules.wallet.infrastructure.models import Transaction
from decimal import Decimal

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        dead_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                dead_connections.append(connection)
        
        for conn in dead_connections:
            self.disconnect(conn)

class CrashManager:
    def __init__(self):
        self.connection_manager = ConnectionManager()
        self.status = "BETTING" # BETTING, IN_PROGRESS, CRASHED
        self.multiplier = 1.00
        self.crash_point = 1.00
        self.timer = 10.0 # seconds for betting
        self.bets: Dict[int, dict] = {} # user_id -> bet_data
        self.task = None

    def start_loop(self):
        if not self.task:
            self.task = asyncio.create_task(self.game_loop())

    def generate_crash_point(self) -> float:
        u = random.random()
        if u < 0.01:
            return 1.00
        return max(1.00, min(1000.0, 0.99 / u))

    async def save_session_to_db(self):
        async with AsyncSessionLocal() as db:
            session = CrashGameSession(status="CRASHED", crash_point=Decimal(str(self.crash_point)))
            db.add(session)
            await db.commit()
            await db.refresh(session)
            
            for user_id, bet in self.bets.items():
                cashout = bet["cashout_multiplier"]
                payout = bet["payout"]
                crash_bet = CrashBet(
                    session_id=session.id,
                    user_id=user_id,
                    bet_amount=Decimal(str(bet["bet_amount"])),
                    cashout_multiplier=Decimal(str(cashout)) if cashout is not None else None,
                    payout=Decimal(str(payout))
                )
                db.add(crash_bet)
                
                if payout > 0:
                    user = await db.get(User, user_id)
                    if user:
                        user.balance += Decimal(str(payout))
                        tx = Transaction(user_id=user_id, amount=Decimal(str(payout)), transaction_type="CASHOUT", description="Crash Payout")
                        db.add(tx)
            
            await db.commit()

    async def game_loop(self):
        while True:
            try:
                # Phase 1: Betting
                self.status = "BETTING"
                self.multiplier = 1.00
                self.bets = {}
                self.timer = 10.0
                
                while self.timer > 0:
                    await self.broadcast_state()
                    await asyncio.sleep(1)
                    self.timer -= 1
                    
                # Phase 2: In Progress
                self.status = "IN_PROGRESS"
                self.crash_point = round(self.generate_crash_point(), 2)
                time_passed = 0.0
                
                while self.status == "IN_PROGRESS":
                    self.multiplier = round(math.exp(0.06 * time_passed), 2)
                    
                    if self.multiplier >= self.crash_point:
                        self.multiplier = self.crash_point
                        self.status = "CRASHED"
                        break
                        
                    await self.broadcast_state()
                    await asyncio.sleep(0.1)
                    time_passed += 0.1
                    
                # Phase 3: Crashed
                await self.broadcast_state()
                await self.save_session_to_db()
                await asyncio.sleep(5)
            except Exception as e:
                print(f"Error in Crash game loop: {e}")
                await asyncio.sleep(5) # Delay and retry on error

    async def broadcast_state(self):
        state = {
            "status": self.status,
            "multiplier": self.multiplier,
            "timer": self.timer,
            "bets": list(self.bets.values())
        }
        await self.connection_manager.broadcast({"type": "state", "data": state})

    async def place_bet(self, user_id: int, username: str, amount: float) -> bool:
        if self.status != "BETTING":
            return False
        if user_id in self.bets:
            return False
            
        async with AsyncSessionLocal() as db:
            user = await db.get(User, user_id)
            if not user or user.balance < Decimal(str(amount)):
                return False
                
            user.balance -= Decimal(str(amount))
            tx = Transaction(user_id=user_id, amount=Decimal(str(amount)), transaction_type="BET", description="Crash Bet")
            db.add(tx)
            await db.commit()
            
        self.bets[user_id] = {
            "user_id": user_id,
            "username": username,
            "bet_amount": amount,
            "cashout_multiplier": None,
            "payout": 0.0
        }
        await self.broadcast_state()
        return True

    async def cash_out(self, user_id: int) -> bool:
        if self.status != "IN_PROGRESS":
            return False
        if user_id not in self.bets:
            return False
        
        bet = self.bets[user_id]
        if bet["cashout_multiplier"] is not None:
            return False 
            
        current_mult = self.multiplier
        payout = round(bet["bet_amount"] * current_mult, 2)
        
        bet["cashout_multiplier"] = current_mult
        bet["payout"] = payout
        
        await self.broadcast_state()
        return True

crash_manager = CrashManager()
