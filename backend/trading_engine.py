"""
Trading Engine
Orchestrates auto-trading: reads market prices, runs optimizer,
generates and executes orders automatically.
"""
import asyncio
import logging
import numpy as np
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from backend import models
from backend.order_manager import OrderManager
from backend.market_data import MarketDataEngine
from backend.websocket_manager import ws_manager
from backend.database import SessionLocal
from src.config import (
    BATTERY_POWER, BATTERY_ENERGY, ETA, DEGR_COST, DEV_PENALTY,
    HORIZON, SCENARIOS, LAMBDA,
)

logger = logging.getLogger("emsjb.trading")


class TradingEngine:
    """
    Automated trading engine.
    Subscribes to market data ticks and uses the CVaR optimizer
    to generate buy/sell decisions.
    """

    def __init__(self, market_engine: MarketDataEngine, order_manager: OrderManager):
        self._market = market_engine
        self._orders = order_manager
        self._model = None
        self._residuals = None
        self._running = False
        self._session_id: Optional[int] = None
        self._strategy = "AUTO_CVAR"
        self._total_orders = 0
        self._total_trades = 0
        self._session_pnl = 0.0
        self._started_at: Optional[datetime] = None

    def set_model(self, model, residuals):
        """Set the forecast model (from startup)."""
        self._model = model
        self._residuals = residuals

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def session_id(self) -> Optional[int]:
        return self._session_id

    async def start(self, strategy: str = "AUTO_CVAR"):
        """Start auto-trading."""
        if self._running:
            logger.warning("Trading engine already running")
            return

        if self._model is None:
            logger.error("Cannot start trading: forecast model not set")
            return

        self._running = True
        self._strategy = strategy
        self._started_at = datetime.utcnow()
        self._total_orders = 0
        self._total_trades = 0
        self._session_pnl = 0.0

        # Create trading session in DB
        db = SessionLocal()
        try:
            session = models.TradingSession(
                is_active=True,
                strategy=strategy,
                speed_multiplier=self._market.speed_multiplier,
            )
            db.add(session)
            db.commit()
            db.refresh(session)
            self._session_id = session.id
        finally:
            db.close()

        # Subscribe to market ticks
        self._market.subscribe(self._on_price_tick)

        logger.info(f"Trading engine STARTED: session={self._session_id}, strategy={strategy}")

        # Broadcast trading status
        await ws_manager.send_alert({
            "level": "info",
            "title": "Auto-Trading Started",
            "message": f"Strategy: {strategy} | Speed: {self._market.speed_multiplier}x",
        })

    async def stop(self):
        """Stop auto-trading."""
        if not self._running:
            return

        self._running = False

        # Update session in DB
        if self._session_id:
            db = SessionLocal()
            try:
                session = db.query(models.TradingSession).filter(
                    models.TradingSession.id == self._session_id
                ).first()
                if session:
                    session.is_active = False
                    session.stopped_at = datetime.utcnow()
                    session.total_orders = self._total_orders
                    session.total_trades = self._total_trades
                    session.session_pnl_inr = self._session_pnl
                    db.commit()
            finally:
                db.close()

        logger.info(
            f"Trading engine STOPPED: session={self._session_id}, "
            f"orders={self._total_orders}, trades={self._total_trades}, "
            f"P&L=₹{self._session_pnl:.2f}"
        )

        await ws_manager.send_alert({
            "level": "warning",
            "title": "Auto-Trading Stopped",
            "message": f"Session P&L: ₹{self._session_pnl:.2f} | Orders: {self._total_orders}",
        })

        self._session_id = None

    async def _on_price_tick(self, tick: dict):
        """Called on every market price tick. Decides whether to trade."""
        if not self._running:
            return

        if self._orders.is_halted:
            logger.info("Skipping trade: risk limit halted trading")
            return

        try:
            price = tick["price_inr_kwh"]
            idx = tick.get("index", self._market.current_index)

            # Generate optimal dispatch decision
            action, quantity = self._compute_dispatch(price, idx)

            if action == "HOLD" or quantity < 1.0:
                return

            # Create and execute order
            db = SessionLocal()
            try:
                order_data = {
                    "side": action,
                    "market": "RTM",
                    "quantity_kwh": quantity,
                    "limit_price_inr": None,  # Market order
                    "strategy": self._strategy,
                    "notes": f"Auto-trade session #{self._session_id}",
                }

                order = self._orders.create_order(db, order_data)
                self._total_orders += 1

                if order.status == models.OrderStatus.PENDING:
                    trade = self._orders.execute_order(db, order, price)
                    if trade:
                        self._total_trades += 1
                        self._session_pnl += trade.net_amount_inr

                        # Broadcast updates via WebSocket
                        await ws_manager.send_order_update({
                            "id": order.id,
                            "side": str(order.side.value),
                            "quantity_kwh": order.quantity_kwh,
                            "status": str(order.status.value),
                            "filled_avg_price": order.filled_avg_price,
                        })

                        await ws_manager.send_trade_fill({
                            "id": trade.id,
                            "order_id": trade.order_id,
                            "side": str(trade.side.value),
                            "quantity_kwh": trade.quantity_kwh,
                            "price_inr": trade.price_inr,
                            "net_amount_inr": trade.net_amount_inr,
                        })

                        await ws_manager.send_position_update(
                            self._orders.get_position(price)
                        )

            finally:
                db.close()

        except Exception as e:
            logger.error(f"Auto-trade error: {e}", exc_info=True)

    def _compute_dispatch(self, current_price: float, data_idx: int) -> tuple:
        """
        Use the CVaR optimizer to decide BUY/SELL/HOLD.
        Returns (action, quantity_kwh).
        """
        from src.forecast import predict_horizon
        from src.optimizer import optimize_battery

        try:
            df = self._market._df
            prices = self._market._prices

            # Need enough historical data for forecast
            if data_idx < 24:
                return "HOLD", 0.0

            # Generate forecast
            forecast = predict_horizon(self._model, df, prices, data_idx, HORIZON)

            # Generate scenarios
            rng = np.random.RandomState(data_idx)
            scenarios = []
            for _ in range(SCENARIOS):
                noise = rng.choice(self._residuals, size=HORIZON, replace=True)
                scenarios.append(forecast + noise)

            # Optimize
            soc = self._orders.soc
            q_opt = optimize_battery(forecast, scenarios, soc)

            # Interpret result
            if q_opt is None or abs(q_opt) < 10.0:  # Minimum 10 kWh threshold
                return "HOLD", 0.0

            if q_opt > 0:
                return "SELL", min(float(q_opt), BATTERY_POWER)
            else:
                return "BUY", min(float(abs(q_opt)), BATTERY_POWER)

        except Exception as e:
            logger.error(f"Dispatch computation error: {e}", exc_info=True)
            return "HOLD", 0.0

    def get_status(self) -> dict:
        """Get current trading engine status."""
        return {
            "is_active": self._running,
            "strategy": self._strategy if self._running else None,
            "session_id": self._session_id,
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "total_orders": self._total_orders,
            "total_trades": self._total_trades,
            "session_pnl_inr": round(self._session_pnl, 2),
            "speed_multiplier": self._market.speed_multiplier,
            "current_price": self._market.current_price,
            "mode": "SIMULATED",
        }
