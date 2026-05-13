from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from app.shared.database import Base

class Bet(Base):
    __tablename__ = "bets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    game_id = Column(String, nullable=False) # e.g. 'slots', 'roulette'
    bet_amount = Column(Numeric(10, 2), nullable=False)
    payout = Column(Numeric(10, 2), default=0.00, nullable=False)
    result_data = Column(JSONB, nullable=True) # Datos extra de la jugada
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class BlackjackGame(Base):
    __tablename__ = "blackjack_games"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    bet_amount = Column(Numeric(10, 2), nullable=False)
    deck = Column(JSONB, nullable=False)
    player_hand = Column(JSONB, nullable=False)
    dealer_hand = Column(JSONB, nullable=False)
    status = Column(String, default="ACTIVE", nullable=False) # ACTIVE, PLAYER_WON, DEALER_WON, PUSH, BUSTED
    is_split = Column(Boolean, default=False, nullable=False)
    active_hand_index = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class BlackjackTable(Base):
    __tablename__ = "blackjack_tables"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    status = Column(String, default="WAITING_PLAYERS", nullable=False) # WAITING_PLAYERS, BETTING, DEALING, PLAYING, RESOLVED
    deck = Column(JSONB, nullable=False)
    dealer_hand = Column(JSONB, nullable=False)
    players_data = Column(JSONB, default=list, nullable=False) # Lista de jugadores sentados y sus manos/apuestas
    current_turn_index = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
