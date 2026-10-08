from sqlalchemy import (
    Column, Integer, Float, String, Boolean, ForeignKey,
    DateTime, Text, Enum as SAEnum, Index,
)
from sqlalchemy.orm import relationship
from backend.database import Base
from datetime import datetime
import enum


# ══════════════════════════════════════════════════════════════
#  ENUMS
# ══════════════════════════════════════════════════════════════

class OrderSide(str, enum.Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(str, enum.Enum):
    PENDING = "PENDING"
    FILLED = "FILLED"
    PARTIAL = "PARTIAL"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class MarketType(str, enum.Enum):
    DAM = "DAM"
    RTM = "RTM"


class TradingStrategy(str, enum.Enum):
    MANUAL = "MANUAL"
    AUTO_CVAR = "AUTO_CVAR"
    AUTO_NAIVE = "AUTO_NAIVE"


class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"
    TRADER = "TRADER"
    VIEWER = "VIEWER"


class PriceSource(str, enum.Enum):
    LIVE = "LIVE"
    SIMULATED = "SIMULATED"


# ══════════════════════════════════════════════════════════════
#  USER
# ══════════════════════════════════════════════════════════════

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(120), unique=True, nullable=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=True)
    role = Column(SAEnum(UserRole), default=UserRole.TRADER, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

    orders = relationship("Order", back_populates="user")


# ══════════════════════════════════════════════════════════════
#  MARKET PRICE (Live tick data)
# ══════════════════════════════════════════════════════════════

class MarketPrice(Base):
    __tablename__ = "market_prices"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    price_inr_kwh = Column(Float, nullable=False)
    volume_mwh = Column(Float, default=0.0)
    market = Column(SAEnum(MarketType), default=MarketType.RTM)
    source = Column(SAEnum(PriceSource), default=PriceSource.SIMULATED)

    __table_args__ = (
        Index("ix_market_prices_ts_market", "timestamp", "market"),
    )


# ══════════════════════════════════════════════════════════════
#  ORDER
# ══════════════════════════════════════════════════════════════

class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    side = Column(SAEnum(OrderSide), nullable=False)
    market = Column(SAEnum(MarketType), default=MarketType.RTM)
    quantity_kwh = Column(Float, nullable=False)
    limit_price_inr = Column(Float, nullable=True)          # None = market order
    status = Column(SAEnum(OrderStatus), default=OrderStatus.PENDING, index=True)
    filled_quantity_kwh = Column(Float, default=0.0)
    filled_avg_price = Column(Float, default=0.0)
    strategy = Column(SAEnum(TradingStrategy), default=TradingStrategy.MANUAL)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    notes = Column(Text, nullable=True)

    user = relationship("User", back_populates="orders")
    trades = relationship("Trade", back_populates="order", cascade="all, delete-orphan")


# ══════════════════════════════════════════════════════════════
#  TRADE (executed fills)
# ══════════════════════════════════════════════════════════════

class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    executed_at = Column(DateTime, default=datetime.utcnow, index=True)
    side = Column(SAEnum(OrderSide), nullable=False)
    market = Column(SAEnum(MarketType), default=MarketType.RTM)
    quantity_kwh = Column(Float, nullable=False)
    price_inr = Column(Float, nullable=False)
    fees_inr = Column(Float, default=0.0)
    net_amount_inr = Column(Float, nullable=False)          # qty * price - fees (+ for sell, - for buy)

    order = relationship("Order", back_populates="trades")


# ══════════════════════════════════════════════════════════════
#  POSITION (running battery state + P&L)
# ══════════════════════════════════════════════════════════════

class Position(Base):
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    soc_kwh = Column(Float, default=0.0)                    # Current state of charge
    total_bought_kwh = Column(Float, default=0.0)
    total_sold_kwh = Column(Float, default=0.0)
    total_bought_value_inr = Column(Float, default=0.0)
    total_sold_value_inr = Column(Float, default=0.0)
    realized_pnl_inr = Column(Float, default=0.0)
    unrealized_pnl_inr = Column(Float, default=0.0)
    degradation_cost_inr = Column(Float, default=0.0)


# ══════════════════════════════════════════════════════════════
#  TRADING SESSION
# ══════════════════════════════════════════════════════════════

class TradingSession(Base):
    __tablename__ = "trading_sessions"

    id = Column(Integer, primary_key=True, index=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    stopped_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    strategy = Column(SAEnum(TradingStrategy), default=TradingStrategy.AUTO_CVAR)
    total_orders = Column(Integer, default=0)
    total_trades = Column(Integer, default=0)
    session_pnl_inr = Column(Float, default=0.0)
    speed_multiplier = Column(Float, default=60.0)


# ══════════════════════════════════════════════════════════════
#  AUDIT LOG
# ══════════════════════════════════════════════════════════════

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    action = Column(String(100), nullable=False)
    details = Column(Text, nullable=True)                    # JSON string
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    ip_address = Column(String(45), nullable=True)


# ══════════════════════════════════════════════════════════════
#  SIMULATION MODELS (preserved from original)
# ══════════════════════════════════════════════════════════════

class SimulationRun(Base):
    __tablename__ = "simulation_runs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    total_profit = Column(Float)
    steps_count = Column(Integer, default=0)

    steps = relationship("SimulationStep", back_populates="run", cascade="all, delete-orphan")


class SimulationStep(Base):
    __tablename__ = "simulation_steps"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("simulation_runs.id"))
    step_index = Column(Integer)
    price = Column(Float)
    forecast_price = Column(Float, default=0.0)
    battery_power = Column(Float)
    soc = Column(Float)
    profit = Column(Float)
    energy_revenue = Column(Float, default=0.0)
    degradation_cost = Column(Float, default=0.0)
    deviation_penalty = Column(Float, default=0.0)

    run = relationship("SimulationRun", back_populates="steps")
