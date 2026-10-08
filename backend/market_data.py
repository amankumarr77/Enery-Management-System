"""
Market Data Engine
Provides real-time price feeds for the trading system.
- SimulatedFeed: replays historical CSV data at configurable speed
- LiveIEXFeed: placeholder for real IEX API integration
"""
import asyncio
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Callable, List, Optional

logger = logging.getLogger("emsjb.market")


class MarketDataEngine:
    """
    Core market data engine. Manages price feeds (simulated or live)
    and broadcasts ticks to subscribers via callbacks.
    """

    def __init__(self, df: pd.DataFrame, speed_multiplier: float = 60.0):
        """
        Parameters
        ----------
        df : DataFrame
            Historical price data (must have Timestamp, Price_INR_kWh columns)
        speed_multiplier : float
            How fast to replay: 60 = 1 historical hour per real minute.
        """
        self._df = df
        self._prices = df["Price_INR_kWh"].values
        self._timestamps = df["Timestamp"].values
        self._speed = speed_multiplier
        self._current_idx = 0
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._subscribers: List[Callable] = []

        # Current state
        self._current_price = float(self._prices[0])
        self._price_history: List[dict] = []
        self._max_history = 2000  # Keep last N ticks in memory

        logger.info(
            f"MarketDataEngine initialized: {len(self._prices)} data points, "
            f"speed={speed_multiplier}x"
        )

    @property
    def current_price(self) -> float:
        return self._current_price

    @property
    def current_index(self) -> int:
        return self._current_idx

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def speed_multiplier(self) -> float:
        return self._speed

    @speed_multiplier.setter
    def speed_multiplier(self, value: float):
        self._speed = max(1.0, min(3600.0, value))
        logger.info(f"Speed multiplier changed to {self._speed}x")

    def subscribe(self, callback: Callable):
        """Register a callback for price ticks: callback(tick_dict)"""
        self._subscribers.append(callback)

    def get_current_tick(self) -> dict:
        """Return the current price as a tick dict."""
        idx = self._current_idx
        prev_price = float(self._prices[max(0, idx - 1)])
        change_pct = ((self._current_price - prev_price) / prev_price * 100) if prev_price > 0 else 0.0

        return {
            "timestamp": str(pd.Timestamp(self._timestamps[idx])),
            "price_inr_kwh": round(self._current_price, 4),
            "volume_mwh": round(float(np.random.uniform(50, 500)), 1),  # Simulated volume
            "market": "RTM",
            "source": "SIMULATED",
            "change_pct": round(change_pct, 2),
            "index": idx,
        }

    def get_price_history(self, hours: int = 24) -> List[dict]:
        """Get recent price history."""
        n_points = min(hours, len(self._price_history))
        return self._price_history[-n_points:]

    def get_stats(self) -> dict:
        """Get 24h price statistics."""
        recent = self._price_history[-24:] if len(self._price_history) >= 24 else self._price_history
        if not recent:
            return {
                "current_price": self._current_price,
                "high_24h": self._current_price,
                "low_24h": self._current_price,
                "avg_24h": self._current_price,
                "change_24h_pct": 0.0,
            }

        prices = [t["price_inr_kwh"] for t in recent]
        first_price = prices[0]
        change_pct = ((self._current_price - first_price) / first_price * 100) if first_price > 0 else 0.0

        return {
            "current_price": round(self._current_price, 4),
            "high_24h": round(max(prices), 4),
            "low_24h": round(min(prices), 4),
            "avg_24h": round(float(np.mean(prices)), 4),
            "change_24h_pct": round(change_pct, 2),
        }

    async def start(self):
        """Start the price feed loop."""
        if self._running:
            logger.warning("MarketDataEngine already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._feed_loop())
        logger.info("MarketDataEngine STARTED")

    async def stop(self):
        """Stop the price feed loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("MarketDataEngine STOPPED")

    async def _feed_loop(self):
        """
        Main feed loop: emit one tick per historical hour at accelerated speed.
        At 60x speed: 1 tick every 60 seconds of real time = 1 simulated hour.
        At 360x speed: 1 tick every 10 seconds.
        """
        try:
            while self._running and self._current_idx < len(self._prices):
                # Calculate interval between ticks
                # 1 historical hour at speed_multiplier x
                interval_seconds = 3600.0 / self._speed

                # Update current price with small random noise for realism
                base_price = float(self._prices[self._current_idx])
                noise = np.random.normal(0, base_price * 0.002)  # 0.2% noise
                self._current_price = round(max(0.01, base_price + noise), 4)

                # Create tick
                tick = self.get_current_tick()
                self._price_history.append(tick)

                # Trim history buffer
                if len(self._price_history) > self._max_history:
                    self._price_history = self._price_history[-self._max_history:]

                # Notify all subscribers
                for callback in self._subscribers:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(tick)
                        else:
                            callback(tick)
                    except Exception as e:
                        logger.error(f"Subscriber callback error: {e}")

                self._current_idx += 1

                # Wait for next tick
                await asyncio.sleep(interval_seconds)

            if self._current_idx >= len(self._prices):
                logger.info("MarketDataEngine: reached end of data, looping...")
                self._current_idx = 0  # Loop back to start

        except asyncio.CancelledError:
            logger.info("MarketDataEngine feed loop cancelled")
        except Exception as e:
            logger.error(f"MarketDataEngine feed loop error: {e}", exc_info=True)

    def reset(self):
        """Reset the feed to the beginning."""
        self._current_idx = 0
        self._current_price = float(self._prices[0])
        self._price_history.clear()
        logger.info("MarketDataEngine reset to start")

    def get_forecast_prices(self, model, residuals, horizon: int = 24) -> List[dict]:
        """
        Generate a price forecast from the current position.
        Returns list of {hour, price_forecast, price_lower, price_upper}
        """
        from src.forecast import predict_horizon

        idx = self._current_idx
        if idx < 24:  # Need at least LAG data points
            idx = 24

        try:
            forecast = predict_horizon(model, self._df, self._prices, idx, horizon)
            std = float(np.std(residuals)) if len(residuals) > 0 else 0.1

            result = []
            for h in range(horizon):
                f = float(forecast[h])
                result.append({
                    "hour": h + 1,
                    "price_forecast": round(f, 4),
                    "price_lower": round(f - 1.96 * std, 4),
                    "price_upper": round(f + 1.96 * std, 4),
                })
            return result
        except Exception as e:
            logger.error(f"Forecast generation error: {e}")
            return [{
                "hour": h + 1,
                "price_forecast": self._current_price,
                "price_lower": self._current_price * 0.9,
                "price_upper": self._current_price * 1.1,
            } for h in range(horizon)]
