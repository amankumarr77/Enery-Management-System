import math
import os

# ── Battery Parameters ──────────────────────────────────────
BATTERY_POWER = 1000.0          # kW — max charge/discharge rate
BATTERY_ENERGY = 4000.0         # kWh — total storage capacity (4-hour system)
ETA = math.sqrt(0.88)           # One-way efficiency (sqrt of round-trip 88%)

CAPEX = (300 * 84 * BATTERY_ENERGY) / 5   # Capital expenditure (₹)
OPEX_PER_YEAR = 0.02 * CAPEX              # Annual O&M cost (₹)

CYCLE_LIFE = 6000                                       # Expected lifetime cycles
DEGR_COST = CAPEX / (2 * CYCLE_LIFE * BATTERY_ENERGY)  # ₹/kWh degradation cost

DEV_PENALTY = 2.0               # ₹/kWh penalty for schedule deviation

# ── Forecasting ─────────────────────────────────────────────
LAG = 24                        # Lookback window (hours)

# ── Optimisation & Risk ─────────────────────────────────────
HORIZON = 24                    # Planning horizon (hours)
SCENARIOS = 5                   # Number of stochastic scenarios
ALPHA = 0.95                    # CVaR confidence level
LAMBDA = 0.3                    # Risk-aversion weight (0 = risk-neutral, 1 = pure CVaR)

# ── Trading Parameters ──────────────────────────────────────
MAX_ORDER_SIZE_KWH = BATTERY_POWER       # Maximum single order quantity (kWh)
DAILY_LOSS_LIMIT_INR = 50000.0           # Stop trading if daily loss exceeds this
MAX_POSITION_KWH = BATTERY_ENERGY        # Max net position (same as battery capacity)
RTM_BLOCK_MINUTES = 15                   # RTM time block duration
DAM_GATE_CLOSURE_HOURS = 1               # DAM scheduling lead time
SIMULATION_SPEED_MULTIPLIER = 60         # Sim speed (60 = 1 real min per historical hour)
AUTO_TRADE_ENABLED = False               # Default auto-trade off
TRADING_MODE = os.getenv("TRADING_MODE", "SIMULATED")  # SIMULATED or LIVE

# ── Authentication ──────────────────────────────────────────
SECRET_KEY = os.getenv("SECRET_KEY", "emsjb-dev-secret-key-change-in-prod-2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480        # 8 hour sessions

# ── Database ────────────────────────────────────────────────
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./emsjb.db"  # Fallback to SQLite for local dev
)