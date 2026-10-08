from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from enum import Enum


# ══════════════════════════════════════════════════════════════
#  ENUMS (mirror SQLAlchemy enums for API serialization)
# ══════════════════════════════════════════════════════════════

class OrderSideEnum(str, Enum):
    BUY = "BUY"
    SELL = "SELL"

class OrderStatusEnum(str, Enum):
    PENDING = "PENDING"
    FILLED = "FILLED"
    PARTIAL = "PARTIAL"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"

class MarketTypeEnum(str, Enum):
    DAM = "DAM"
    RTM = "RTM"

class TradingStrategyEnum(str, Enum):
    MANUAL = "MANUAL"
    AUTO_CVAR = "AUTO_CVAR"
    AUTO_NAIVE = "AUTO_NAIVE"

class UserRoleEnum(str, Enum):
    ADMIN = "ADMIN"
    TRADER = "TRADER"
    VIEWER = "VIEWER"


# ══════════════════════════════════════════════════════════════
#  AUTH
# ══════════════════════════════════════════════════════════════

class LoginRequest(BaseModel):
    username: str
    password: str

class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: UserRoleEnum = UserRoleEnum.TRADER

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserResponse"

class UserResponse(BaseModel):
    id: int
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: UserRoleEnum
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True


# ══════════════════════════════════════════════════════════════
#  MARKET DATA
# ══════════════════════════════════════════════════════════════

class MarketPriceTick(BaseModel):
    timestamp: str
    price_inr_kwh: float
    volume_mwh: float = 0.0
    market: MarketTypeEnum = MarketTypeEnum.RTM
    source: str = "SIMULATED"
    change_pct: float = 0.0

class MarketPriceHistory(BaseModel):
    prices: List[MarketPriceTick]
    current_price: float
    high_24h: float
    low_24h: float
    avg_24h: float
    change_24h_pct: float

class ForecastPoint(BaseModel):
    hour: int
    price_forecast: float
    price_lower: float              # Confidence band lower
    price_upper: float              # Confidence band upper

class ForecastResponse(BaseModel):
    current_price: float
    forecasts: List[ForecastPoint]
    model_accuracy_mape: float = 0.0


# ══════════════════════════════════════════════════════════════
#  ORDERS
# ══════════════════════════════════════════════════════════════

class OrderCreate(BaseModel):
    side: OrderSideEnum
    market: MarketTypeEnum = MarketTypeEnum.RTM
    quantity_kwh: float = Field(..., gt=0)
    limit_price_inr: Optional[float] = None     # None = market order
    strategy: TradingStrategyEnum = TradingStrategyEnum.MANUAL
    notes: Optional[str] = None

class OrderResponse(BaseModel):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    side: OrderSideEnum
    market: MarketTypeEnum
    quantity_kwh: float
    limit_price_inr: Optional[float] = None
    status: OrderStatusEnum
    filled_quantity_kwh: float = 0.0
    filled_avg_price: float = 0.0
    strategy: TradingStrategyEnum
    user_id: Optional[int] = None
    notes: Optional[str] = None
    trades: List["TradeResponse"] = []

    class Config:
        from_attributes = True


# ══════════════════════════════════════════════════════════════
#  TRADES
# ══════════════════════════════════════════════════════════════

class TradeResponse(BaseModel):
    id: int
    order_id: int
    executed_at: datetime
    side: OrderSideEnum
    market: MarketTypeEnum
    quantity_kwh: float
    price_inr: float
    fees_inr: float
    net_amount_inr: float

    class Config:
        from_attributes = True


# ══════════════════════════════════════════════════════════════
#  POSITION & P&L
# ══════════════════════════════════════════════════════════════

class PositionResponse(BaseModel):
    soc_kwh: float
    soc_pct: float                              # SOC as % of capacity
    total_bought_kwh: float
    total_sold_kwh: float
    total_bought_value_inr: float
    total_sold_value_inr: float
    realized_pnl_inr: float
    unrealized_pnl_inr: float
    total_pnl_inr: float
    degradation_cost_inr: float
    avg_buy_price: float
    avg_sell_price: float
    timestamp: Optional[datetime] = None

    class Config:
        from_attributes = True


# ══════════════════════════════════════════════════════════════
#  TRADING SESSION
# ══════════════════════════════════════════════════════════════

class TradingStatusResponse(BaseModel):
    is_active: bool
    strategy: Optional[TradingStrategyEnum] = None
    session_id: Optional[int] = None
    started_at: Optional[datetime] = None
    total_orders: int = 0
    total_trades: int = 0
    session_pnl_inr: float = 0.0
    speed_multiplier: float = 60.0
    current_price: Optional[float] = None
    mode: str = "SIMULATED"                     # SIMULATED or LIVE

class TradingSettingsUpdate(BaseModel):
    speed_multiplier: Optional[float] = Field(None, ge=1, le=3600)
    cvar_lambda: Optional[float] = Field(None, ge=0, le=1)
    cvar_alpha: Optional[float] = Field(None, ge=0.5, le=0.99)
    planning_horizon_hours: Optional[int] = Field(None, ge=1, le=48)
    scenarios: Optional[int] = Field(None, ge=1, le=50)
    auto_trade_enabled: Optional[bool] = None


# ══════════════════════════════════════════════════════════════
#  RISK MANAGEMENT
# ══════════════════════════════════════════════════════════════

class RiskLimits(BaseModel):
    max_order_size_kwh: float
    daily_loss_limit_inr: float
    max_position_kwh: float
    current_daily_pnl: float = 0.0
    current_position_kwh: float = 0.0
    loss_limit_utilization_pct: float = 0.0
    position_utilization_pct: float = 0.0
    is_trading_halted: bool = False
    halt_reason: Optional[str] = None

class RiskLimitsUpdate(BaseModel):
    max_order_size_kwh: Optional[float] = Field(None, gt=0)
    daily_loss_limit_inr: Optional[float] = Field(None, gt=0)
    max_position_kwh: Optional[float] = Field(None, gt=0)


# ══════════════════════════════════════════════════════════════
#  AUDIT LOG
# ══════════════════════════════════════════════════════════════

class AuditLogResponse(BaseModel):
    id: int
    timestamp: datetime
    action: str
    details: Optional[str] = None
    user_id: Optional[int] = None

    class Config:
        from_attributes = True


# ══════════════════════════════════════════════════════════════
#  SIMULATION (preserved from original)
# ══════════════════════════════════════════════════════════════

class SimulationStepBase(BaseModel):
    step_index: int
    price: float
    forecast_price: float = 0.0
    battery_power: float
    soc: float
    profit: float
    energy_revenue: float = 0.0
    degradation_cost: float = 0.0
    deviation_penalty: float = 0.0

class SimulationStepCreate(SimulationStepBase):
    pass

class SimulationStep(SimulationStepBase):
    id: int
    run_id: int
    class Config:
        from_attributes = True

class SimulationRunBase(BaseModel):
    total_profit: float
    steps_count: int = 0

class SimulationRunCreate(SimulationRunBase):
    pass

class SimulationRun(SimulationRunBase):
    id: int
    timestamp: datetime
    steps: List[SimulationStep] = []
    class Config:
        from_attributes = True


# ── Config ──────────────────────────────────────────────────

class ConfigResponse(BaseModel):
    battery_power_kw: float
    battery_energy_kwh: float
    round_trip_efficiency: float
    capex_inr: float
    opex_per_year_inr: float
    cycle_life: int
    degradation_cost_per_kwh: float
    deviation_penalty: float
    forecast_lag_hours: int
    planning_horizon_hours: int
    scenarios: int
    cvar_alpha: float
    cvar_lambda: float

class ConfigUpdate(BaseModel):
    battery_power_kw: Optional[float] = None
    battery_energy_kwh: Optional[float] = None
    round_trip_efficiency: Optional[float] = None
    cycle_life: Optional[int] = None
    cvar_alpha: Optional[float] = None
    cvar_lambda: Optional[float] = None
    planning_horizon_hours: Optional[int] = None
    scenarios: Optional[int] = None


# ── Data Summary ────────────────────────────────────────────

class DataSummary(BaseModel):
    total_hours: int
    date_start: str
    date_end: str
    price_mean: float
    price_min: float
    price_max: float
    price_std: float


# ── Metrics ─────────────────────────────────────────────────

class MetricsResponse(BaseModel):
    total_profit: float
    avg_daily_profit: float
    total_cycles: float
    profit_per_cycle: float
    max_drawdown: float
    sharpe_ratio: float
    utilization_rate: float
    payback_years: float = 0.0
    roi_annual_pct: float = 0.0
    total_energy_revenue: float = 0.0
    total_degradation_cost: float = 0.0
    total_deviation_penalty: float = 0.0
    forecast_mae: float = 0.0
    forecast_rmse: float = 0.0


# ── Baseline Comparison ─────────────────────────────────────

class BaselineResult(BaseModel):
    strategy: str
    total_profit: float
    total_cycles: float
    sharpe_ratio: float
    utilization_rate: float

class BaselineComparison(BaseModel):
    optimized: BaselineResult
    naive: BaselineResult
    no_storage: BaselineResult


# ── Forecast Accuracy ───────────────────────────────────────

class ForecastAccuracy(BaseModel):
    train_mae: float = 0.0
    train_rmse: float = 0.0
    train_mape: float = 0.0


# ── WebSocket Message Types ─────────────────────────────────

class WSMessage(BaseModel):
    type: str                                   # price_tick, order_update, trade_fill, position_update, alert
    data: dict
    timestamp: str
