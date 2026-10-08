import logging
import math
import json

from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from contextlib import asynccontextmanager
import pandas as pd
import numpy as np
import io
import sys
import os

# Add root directory to sys.path to import src modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import models, schemas
from backend.database import Base, engine, SessionLocal, get_db
from backend.websocket_manager import ws_manager
from backend.market_data import MarketDataEngine
from backend.order_manager import OrderManager
from backend.trading_engine import TradingEngine
from backend.auth import (
    authenticate_user, create_user, create_access_token,
    get_current_user, get_current_user_optional, require_role,
    ensure_default_admin, get_user_by_username,
)
from src.data_loader import load_price_data
from src.forecast import train_forecast_model
from src.simulation import simulate_operation
from src.baseline import naive_strategy, no_storage_baseline
from src.metrics import compute_all_metrics, total_profit, total_cycles, sharpe_ratio, utilization_rate
import src.config as cfg

# ── Logging ─────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("emsjb")

# ── Global State ────────────────────────────────────────────
app_state = {}
market_engine: Optional[MarketDataEngine] = None
order_manager = OrderManager()
trading_engine: Optional[TradingEngine] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global market_engine, trading_engine

    logger.info("Loading data and training model...")
    df = load_price_data("data/iex_dam_hourly_2024_25.csv")
    model, residuals, accuracy, train_end = train_forecast_model(df)
    app_state["df"] = df
    app_state["model"] = model
    app_state["residuals"] = residuals
    app_state["forecast_accuracy"] = accuracy
    app_state["train_end"] = train_end

    # Create tables
    Base.metadata.create_all(bind=engine)

    # Ensure default admin
    db = SessionLocal()
    try:
        ensure_default_admin(db)
    finally:
        db.close()

    # Initialize market data engine
    market_engine = MarketDataEngine(df, speed_multiplier=cfg.SIMULATION_SPEED_MULTIPLIER)

    # Wire WebSocket broadcasting to market engine
    async def broadcast_tick(tick):
        await ws_manager.send_price_tick(tick)

    market_engine.subscribe(broadcast_tick)

    # Initialize trading engine
    trading_engine = TradingEngine(market_engine, order_manager)
    trading_engine.set_model(model, residuals)

    # Start market data feed
    await market_engine.start()

    logger.info(f"Startup complete. Dataset: {len(df)} hours, Train end idx: {train_end}")
    logger.info(f"Forecast accuracy: {accuracy}")
    logger.info(f"Market feed speed: {cfg.SIMULATION_SPEED_MULTIPLIER}x")
    yield

    # Shutdown
    if trading_engine and trading_engine.is_running:
        await trading_engine.stop()
    if market_engine:
        await market_engine.stop()
    app_state.clear()
    logger.info("Shutdown complete")


app = FastAPI(title="EMSJB Energy Trading Platform", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ══════════════════════════════════════════════════════════════
#  AUTH ENDPOINTS
# ══════════════════════════════════════════════════════════════

@app.post("/api/auth/login", response_model=schemas.TokenResponse)
def login(req: schemas.LoginRequest, db: Session = Depends(get_db)):
    """Authenticate and return JWT token."""
    user = authenticate_user(db, req.username, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    user.last_login = pd.Timestamp.utcnow()
    db.commit()

    token = create_access_token(data={"sub": user.username, "role": user.role.value})
    return schemas.TokenResponse(
        access_token=token,
        user=schemas.UserResponse.model_validate(user),
    )


@app.post("/api/auth/register", response_model=schemas.UserResponse)
def register(req: schemas.RegisterRequest, db: Session = Depends(get_db)):
    """Register a new user."""
    if get_user_by_username(db, req.username):
        raise HTTPException(status_code=400, detail="Username already exists")

    user = create_user(db, req.username, req.password, req.email, req.full_name, req.role.value)
    return schemas.UserResponse.model_validate(user)


@app.get("/api/auth/me", response_model=schemas.UserResponse)
def get_me(user: Optional[models.User] = Depends(get_current_user_optional)):
    """Get current authenticated user."""
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return schemas.UserResponse.model_validate(user)


# ══════════════════════════════════════════════════════════════
#  MARKET DATA ENDPOINTS
# ══════════════════════════════════════════════════════════════

@app.get("/api/market/current", response_model=schemas.MarketPriceTick)
def get_current_price():
    """Get the current (latest) market price."""
    if market_engine is None:
        raise HTTPException(status_code=503, detail="Market engine not ready")
    tick = market_engine.get_current_tick()
    return schemas.MarketPriceTick(**tick)


@app.get("/api/market/history", response_model=schemas.MarketPriceHistory)
def get_price_history(hours: int = 24):
    """Get recent price history with statistics."""
    if market_engine is None:
        raise HTTPException(status_code=503, detail="Market engine not ready")

    history = market_engine.get_price_history(hours)
    stats = market_engine.get_stats()

    return schemas.MarketPriceHistory(
        prices=[schemas.MarketPriceTick(**t) for t in history],
        **stats,
    )


@app.get("/api/market/forecast", response_model=schemas.ForecastResponse)
def get_market_forecast(horizon: int = 24):
    """Get price forecast from current position."""
    if market_engine is None or "model" not in app_state:
        raise HTTPException(status_code=503, detail="Not ready")

    forecasts = market_engine.get_forecast_prices(
        app_state["model"], app_state["residuals"], horizon
    )
    acc = app_state.get("forecast_accuracy", {})

    return schemas.ForecastResponse(
        current_price=market_engine.current_price,
        forecasts=[schemas.ForecastPoint(**f) for f in forecasts],
        model_accuracy_mape=acc.get("mape", 0.0),
    )


# ══════════════════════════════════════════════════════════════
#  ORDER ENDPOINTS
# ══════════════════════════════════════════════════════════════

@app.post("/api/orders", response_model=schemas.OrderResponse)
def place_order(
    req: schemas.OrderCreate,
    db: Session = Depends(get_db),
    user: Optional[models.User] = Depends(get_current_user_optional),
):
    """Place a new buy/sell order."""
    order = order_manager.create_order(
        db,
        {
            "side": req.side.value,
            "market": req.market.value,
            "quantity_kwh": req.quantity_kwh,
            "limit_price_inr": req.limit_price_inr,
            "strategy": req.strategy.value,
            "notes": req.notes,
        },
        user_id=user.id if user else None,
    )

    # For market orders (no limit price), execute immediately
    if order.status == models.OrderStatus.PENDING and req.limit_price_inr is None:
        if market_engine:
            trade = order_manager.execute_order(db, order, market_engine.current_price)

    db.refresh(order)
    return schemas.OrderResponse.model_validate(order)


@app.get("/api/orders", response_model=List[schemas.OrderResponse])
def list_orders(
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """List orders with optional status filter."""
    query = db.query(models.Order)
    if status:
        query = query.filter(models.Order.status == status)
    orders = query.order_by(models.Order.created_at.desc()).offset(skip).limit(limit).all()
    return [schemas.OrderResponse.model_validate(o) for o in orders]


@app.get("/api/orders/{order_id}", response_model=schemas.OrderResponse)
def get_order(order_id: int, db: Session = Depends(get_db)):
    """Get a specific order."""
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return schemas.OrderResponse.model_validate(order)


@app.delete("/api/orders/{order_id}", response_model=schemas.OrderResponse)
def cancel_order(
    order_id: int,
    db: Session = Depends(get_db),
    user: Optional[models.User] = Depends(get_current_user_optional),
):
    """Cancel a pending order."""
    order = order_manager.cancel_order(db, order_id, user_id=user.id if user else None)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return schemas.OrderResponse.model_validate(order)


# ══════════════════════════════════════════════════════════════
#  TRADE ENDPOINTS
# ══════════════════════════════════════════════════════════════

@app.get("/api/trades", response_model=List[schemas.TradeResponse])
def list_trades(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    """List executed trades."""
    trades = db.query(models.Trade).order_by(
        models.Trade.executed_at.desc()
    ).offset(skip).limit(limit).all()
    return [schemas.TradeResponse.model_validate(t) for t in trades]


# ══════════════════════════════════════════════════════════════
#  POSITION & P&L ENDPOINTS
# ══════════════════════════════════════════════════════════════

@app.get("/api/position", response_model=schemas.PositionResponse)
def get_position():
    """Get current position and P&L."""
    price = market_engine.current_price if market_engine else 0.0
    pos = order_manager.get_position(price)
    return schemas.PositionResponse(**pos)


@app.get("/api/position/history", response_model=List[schemas.PositionResponse])
def get_position_history(limit: int = 100, db: Session = Depends(get_db)):
    """Get position snapshots over time."""
    positions = db.query(models.Position).order_by(
        models.Position.timestamp.desc()
    ).limit(limit).all()

    results = []
    for p in positions:
        results.append(schemas.PositionResponse(
            soc_kwh=p.soc_kwh,
            soc_pct=round(p.soc_kwh / cfg.BATTERY_ENERGY * 100, 1),
            total_bought_kwh=p.total_bought_kwh,
            total_sold_kwh=p.total_sold_kwh,
            total_bought_value_inr=p.total_bought_value_inr,
            total_sold_value_inr=p.total_sold_value_inr,
            realized_pnl_inr=p.realized_pnl_inr,
            unrealized_pnl_inr=p.unrealized_pnl_inr,
            total_pnl_inr=p.realized_pnl_inr + p.unrealized_pnl_inr,
            degradation_cost_inr=p.degradation_cost_inr,
            avg_buy_price=0.0,
            avg_sell_price=0.0,
            timestamp=p.timestamp,
        ))
    return results


# ══════════════════════════════════════════════════════════════
#  TRADING ENGINE ENDPOINTS
# ══════════════════════════════════════════════════════════════

@app.post("/api/trading/start", response_model=schemas.TradingStatusResponse)
async def start_trading(strategy: str = "AUTO_CVAR"):
    """Start the auto-trading engine."""
    if trading_engine is None:
        raise HTTPException(status_code=503, detail="Trading engine not initialized")
    await trading_engine.start(strategy)
    return schemas.TradingStatusResponse(**trading_engine.get_status())


@app.post("/api/trading/stop", response_model=schemas.TradingStatusResponse)
async def stop_trading():
    """Stop the auto-trading engine."""
    if trading_engine is None:
        raise HTTPException(status_code=503, detail="Trading engine not initialized")
    await trading_engine.stop()
    return schemas.TradingStatusResponse(**trading_engine.get_status())


@app.get("/api/trading/status", response_model=schemas.TradingStatusResponse)
def get_trading_status():
    """Get current trading engine status."""
    if trading_engine is None:
        return schemas.TradingStatusResponse(is_active=False, mode="SIMULATED")
    return schemas.TradingStatusResponse(**trading_engine.get_status())


@app.put("/api/trading/settings")
def update_trading_settings(settings: schemas.TradingSettingsUpdate):
    """Update trading parameters at runtime."""
    if settings.speed_multiplier is not None and market_engine:
        market_engine.speed_multiplier = settings.speed_multiplier
    if settings.cvar_lambda is not None:
        cfg.LAMBDA = settings.cvar_lambda
    if settings.cvar_alpha is not None:
        cfg.ALPHA = settings.cvar_alpha
    if settings.planning_horizon_hours is not None:
        cfg.HORIZON = settings.planning_horizon_hours
    if settings.scenarios is not None:
        cfg.SCENARIOS = settings.scenarios

    return {"status": "updated", "speed": market_engine.speed_multiplier if market_engine else 60}


# ══════════════════════════════════════════════════════════════
#  RISK MANAGEMENT ENDPOINTS
# ══════════════════════════════════════════════════════════════

@app.get("/api/risk/limits", response_model=schemas.RiskLimits)
def get_risk_limits():
    """Get current risk limits and utilization."""
    return schemas.RiskLimits(**order_manager.get_risk_status())


@app.put("/api/risk/limits", response_model=schemas.RiskLimits)
def update_risk_limits(update: schemas.RiskLimitsUpdate):
    """Update risk limits."""
    if update.max_order_size_kwh is not None:
        cfg.MAX_ORDER_SIZE_KWH = update.max_order_size_kwh
    if update.daily_loss_limit_inr is not None:
        cfg.DAILY_LOSS_LIMIT_INR = update.daily_loss_limit_inr
    if update.max_position_kwh is not None:
        cfg.MAX_POSITION_KWH = update.max_position_kwh
    return schemas.RiskLimits(**order_manager.get_risk_status())


# ══════════════════════════════════════════════════════════════
#  AUDIT LOG
# ══════════════════════════════════════════════════════════════

@app.get("/api/audit/log", response_model=List[schemas.AuditLogResponse])
def get_audit_log(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Get audit trail."""
    logs = db.query(models.AuditLog).order_by(
        models.AuditLog.timestamp.desc()
    ).offset(skip).limit(limit).all()
    return [schemas.AuditLogResponse.model_validate(l) for l in logs]


# ══════════════════════════════════════════════════════════════
#  WEBSOCKET ENDPOINTS
# ══════════════════════════════════════════════════════════════

@app.websocket("/ws/market")
async def ws_market(websocket: WebSocket):
    """WebSocket for real-time market price ticks."""
    await ws_manager.connect(websocket, "market")
    try:
        while True:
            # Keep connection alive, listen for client messages (e.g. ping)
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)


@app.websocket("/ws/trading")
async def ws_trading(websocket: WebSocket):
    """WebSocket for trading updates (orders, trades, positions, alerts)."""
    await ws_manager.connect(websocket, "trading")
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)


# ══════════════════════════════════════════════════════════════
#  CONFIG (preserved from original)
# ══════════════════════════════════════════════════════════════

@app.get("/api/config", response_model=schemas.ConfigResponse)
def get_config():
    """Return current battery & simulation configuration."""
    return schemas.ConfigResponse(
        battery_power_kw=cfg.BATTERY_POWER,
        battery_energy_kwh=cfg.BATTERY_ENERGY,
        round_trip_efficiency=cfg.ETA ** 2,
        capex_inr=cfg.CAPEX,
        opex_per_year_inr=cfg.OPEX_PER_YEAR,
        cycle_life=cfg.CYCLE_LIFE,
        degradation_cost_per_kwh=cfg.DEGR_COST,
        deviation_penalty=cfg.DEV_PENALTY,
        forecast_lag_hours=cfg.LAG,
        planning_horizon_hours=cfg.HORIZON,
        scenarios=cfg.SCENARIOS,
        cvar_alpha=cfg.ALPHA,
        cvar_lambda=cfg.LAMBDA,
    )


@app.post("/api/config", response_model=schemas.ConfigResponse)
def update_config(update: schemas.ConfigUpdate):
    """Update simulation parameters at runtime."""
    if update.battery_power_kw is not None:
        cfg.BATTERY_POWER = update.battery_power_kw
    if update.battery_energy_kwh is not None:
        cfg.BATTERY_ENERGY = update.battery_energy_kwh
    if update.round_trip_efficiency is not None:
        cfg.ETA = math.sqrt(update.round_trip_efficiency)
    if update.cycle_life is not None:
        cfg.CYCLE_LIFE = update.cycle_life
    if update.cvar_alpha is not None:
        cfg.ALPHA = update.cvar_alpha
    if update.cvar_lambda is not None:
        cfg.LAMBDA = update.cvar_lambda
    if update.planning_horizon_hours is not None:
        cfg.HORIZON = update.planning_horizon_hours
    if update.scenarios is not None:
        cfg.SCENARIOS = update.scenarios

    cfg.CAPEX = (300 * 84 * cfg.BATTERY_ENERGY) / 5
    cfg.OPEX_PER_YEAR = 0.02 * cfg.CAPEX
    cfg.DEGR_COST = cfg.CAPEX / (2 * cfg.CYCLE_LIFE * cfg.BATTERY_ENERGY)

    logger.info(f"Config updated: Power={cfg.BATTERY_POWER}, Energy={cfg.BATTERY_ENERGY}, λ={cfg.LAMBDA}")
    return get_config()


# ══════════════════════════════════════════════════════════════
#  DATA SUMMARY (preserved from original)
# ══════════════════════════════════════════════════════════════

@app.get("/api/data/summary", response_model=schemas.DataSummary)
def get_data_summary():
    """Return summary statistics of the loaded price dataset."""
    if "df" not in app_state:
        raise HTTPException(status_code=503, detail="Data not loaded yet.")
    df = app_state["df"]
    prices = df["Price_INR_kWh"]
    return schemas.DataSummary(
        total_hours=len(df),
        date_start=str(df["Timestamp"].min()),
        date_end=str(df["Timestamp"].max()),
        price_mean=round(float(prices.mean()), 4),
        price_min=round(float(prices.min()), 4),
        price_max=round(float(prices.max()), 4),
        price_std=round(float(prices.std()), 4),
    )


# ══════════════════════════════════════════════════════════════
#  FORECAST ACCURACY (preserved from original)
# ══════════════════════════════════════════════════════════════

@app.get("/api/forecast/accuracy", response_model=schemas.ForecastAccuracy)
def get_forecast_accuracy():
    """Return the out-of-sample forecast accuracy metrics."""
    if "forecast_accuracy" not in app_state:
        raise HTTPException(status_code=503, detail="Model not trained yet.")
    acc = app_state["forecast_accuracy"]
    return schemas.ForecastAccuracy(
        train_mae=acc["mae"],
        train_rmse=acc["rmse"],
        train_mape=acc["mape"],
    )


# ══════════════════════════════════════════════════════════════
#  SIMULATION (preserved from original)
# ══════════════════════════════════════════════════════════════

@app.get("/api/simulation/run", response_model=schemas.SimulationRun)
def run_simulation(steps: int = 168, db: Session = Depends(get_db)):
    """Run simulation for a specified number of steps."""
    if "df" not in app_state:
        raise HTTPException(status_code=503, detail="Server is starting up, try again.")

    df = app_state["df"]
    model = app_state["model"]
    residuals = app_state["residuals"]

    sim_df = df.head(cfg.LAG + steps + cfg.HORIZON)
    logger.info(f"Starting simulation: {steps} steps")
    results_df = simulate_operation(sim_df, model, residuals)
    results_df = results_df.head(steps)
    total = results_df["Profit"].sum()

    db_run = models.SimulationRun(total_profit=total, steps_count=len(results_df))
    db.add(db_run)
    db.commit()
    db.refresh(db_run)

    db_steps = []
    for idx, row in results_df.iterrows():
        step = models.SimulationStep(
            run_id=db_run.id,
            step_index=idx,
            price=row["Price"],
            forecast_price=row.get("Forecast_Price", 0.0),
            battery_power=row["Battery_Power"],
            soc=row["SOC"],
            profit=row["Profit"],
            energy_revenue=row.get("Energy_Revenue", 0.0),
            degradation_cost=row.get("Degradation_Cost", 0.0),
            deviation_penalty=row.get("Deviation_Penalty", 0.0),
        )
        db_steps.append(step)

    db.add_all(db_steps)
    db.commit()

    logger.info(f"Simulation complete: Run #{db_run.id}, Profit={total:.2f}, Steps={len(results_df)}")
    return db_run


@app.get("/api/simulation/history", response_model=List[schemas.SimulationRun])
def get_history(skip: int = 0, limit: int = 20, db: Session = Depends(get_db)):
    runs = db.query(models.SimulationRun).order_by(
        models.SimulationRun.timestamp.desc()
    ).offset(skip).limit(limit).all()
    return runs


@app.get("/api/simulation/{run_id}", response_model=schemas.SimulationRun)
def get_simulation(run_id: int, db: Session = Depends(get_db)):
    run = db.query(models.SimulationRun).filter(models.SimulationRun.id == run_id).first()
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@app.get("/api/simulation/{run_id}/metrics", response_model=schemas.MetricsResponse)
def get_metrics(run_id: int, db: Session = Depends(get_db)):
    """Compute performance metrics for a given simulation run."""
    run = db.query(models.SimulationRun).filter(models.SimulationRun.id == run_id).first()
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    steps = db.query(models.SimulationStep).filter(
        models.SimulationStep.run_id == run_id
    ).order_by(models.SimulationStep.step_index).all()

    if not steps:
        raise HTTPException(status_code=404, detail="No steps found for this run")

    df = pd.DataFrame([{
        "Battery_Power": s.battery_power,
        "SOC": s.soc,
        "Profit": s.profit,
        "Price": s.price,
        "Forecast_Price": s.forecast_price or 0.0,
        "Energy_Revenue": s.energy_revenue or 0.0,
        "Degradation_Cost": s.degradation_cost or 0.0,
        "Deviation_Penalty": s.deviation_penalty or 0.0,
    } for s in steps])

    metrics = compute_all_metrics(df)
    return schemas.MetricsResponse(**metrics)


@app.get("/api/simulation/{run_id}/baseline", response_model=schemas.BaselineComparison)
def get_baseline_comparison(run_id: int, db: Session = Depends(get_db)):
    """Compare optimized run against naive and no-storage baselines."""
    run = db.query(models.SimulationRun).filter(models.SimulationRun.id == run_id).first()
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    steps = db.query(models.SimulationStep).filter(
        models.SimulationStep.run_id == run_id
    ).order_by(models.SimulationStep.step_index).all()

    if not steps:
        raise HTTPException(status_code=404, detail="No steps found")

    opt_df = pd.DataFrame([{
        "Battery_Power": s.battery_power,
        "SOC": s.soc,
        "Profit": s.profit,
        "Price": s.price,
        "Forecast_Price": s.forecast_price or 0.0,
        "Energy_Revenue": s.energy_revenue or 0.0,
        "Degradation_Cost": s.degradation_cost or 0.0,
        "Deviation_Penalty": s.deviation_penalty or 0.0,
    } for s in steps])

    n_steps = len(steps)
    df = app_state["df"]
    raw_slice = df.head(n_steps + cfg.HORIZON)

    naive_df = naive_strategy(raw_slice).head(n_steps)
    no_stor_df = no_storage_baseline(raw_slice).head(n_steps)

    def make_result(name, result_df):
        return schemas.BaselineResult(
            strategy=name,
            total_profit=round(total_profit(result_df), 2),
            total_cycles=round(total_cycles(result_df), 2),
            sharpe_ratio=round(sharpe_ratio(result_df), 4),
            utilization_rate=round(utilization_rate(result_df), 4),
        )

    return schemas.BaselineComparison(
        optimized=make_result("CVaR Optimized", opt_df),
        naive=make_result("Naive Peak/Off-Peak", naive_df),
        no_storage=make_result("No Storage", no_stor_df),
    )


@app.get("/api/simulation/{run_id}/export")
def export_csv(run_id: int, db: Session = Depends(get_db)):
    """Download simulation results as CSV."""
    steps = db.query(models.SimulationStep).filter(
        models.SimulationStep.run_id == run_id
    ).order_by(models.SimulationStep.step_index).all()

    if not steps:
        raise HTTPException(status_code=404, detail="No steps found")

    df = pd.DataFrame([{
        "Step": s.step_index,
        "Price_INR_kWh": s.price,
        "Forecast_Price": s.forecast_price or 0.0,
        "Battery_Power_kW": s.battery_power,
        "SOC_kWh": s.soc,
        "Profit_INR": s.profit,
        "Energy_Revenue_INR": s.energy_revenue or 0.0,
        "Degradation_Cost_INR": s.degradation_cost or 0.0,
        "Deviation_Penalty_INR": s.deviation_penalty or 0.0,
    } for s in steps])

    stream = io.StringIO()
    df.to_csv(stream, index=False)
    stream.seek(0)

    return StreamingResponse(
        iter([stream.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=simulation_run_{run_id}.csv"}
    )
