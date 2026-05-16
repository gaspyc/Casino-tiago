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

class PokerTable(Base):
    __tablename__ = "poker_tables"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    status = Column(String, default="WAITING_PLAYERS", nullable=False) # WAITING_PLAYERS, PRE_FLOP, FLOP, TURN, RIVER, SHOWDOWN
    deck = Column(JSONB, nullable=False)
    community_cards = Column(JSONB, default=list, nullable=False)
    players_data = Column(JSONB, default=list, nullable=False)
    current_turn_index = Column(Integer, default=0, nullable=False)
    pot = Column(Numeric(10, 2), default=0.00, nullable=False)
    current_bet = Column(Numeric(10, 2), default=0.00, nullable=False)
    dealer_button_index = Column(Integer, default=0, nullable=False)
    small_blind = Column(Numeric(10, 2), default=5.00, nullable=False)
    big_blind = Column(Numeric(10, 2), default=10.00, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class CrashGameSession(Base):
    __tablename__ = "crash_game_sessions"

    id = Column(Integer, primary_key=True, index=True)
    status = Column(String, default="BETTING", nullable=False) # BETTING, IN_PROGRESS, CRASHED
    crash_point = Column(Numeric(10, 2), nullable=False) # The multiplier where it crashes
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class CrashBet(Base):
    __tablename__ = "crash_bets"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("crash_game_sessions.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    bet_amount = Column(Numeric(10, 2), nullable=False)
    cashout_multiplier = Column(Numeric(10, 2), nullable=True) # None if the user didn't cash out before crash
    payout = Column(Numeric(10, 2), default=0.00, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
