"""
Order Manager
Handles CRUD for orders, trade execution, and position tracking.
"""
import logging
import json
from datetime import datetime, date
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from backend import models
from src.config import BATTERY_ENERGY, DEGR_COST, MAX_ORDER_SIZE_KWH, DAILY_LOSS_LIMIT_INR, MAX_POSITION_KWH

logger = logging.getLogger("emsjb.orders")


class OrderManager:
    """Manages orders, trades, and running position/P&L."""

    def __init__(self):
        self._soc: float = 0.2 * BATTERY_ENERGY  # Start at min SOC
        self._realized_pnl: float = 0.0
        self._daily_pnl: float = 0.0
        self._total_bought_kwh: float = 0.0
        self._total_sold_kwh: float = 0.0
        self._total_bought_value: float = 0.0
        self._total_sold_value: float = 0.0
        self._degradation_cost: float = 0.0
        self._today: date = date.today()
        self._trading_halted: bool = False
        self._halt_reason: Optional[str] = None

    # ══════════════════════════════════════════════════════════
    #  ORDER CREATION
    # ══════════════════════════════════════════════════════════

    def create_order(self, db: Session, order_data: dict, user_id: Optional[int] = None) -> models.Order:
        """Create a new order after validation."""
        # Reset daily P&L if new day
        today = date.today()
        if today != self._today:
            self._daily_pnl = 0.0
            self._today = today
            self._trading_halted = False
            self._halt_reason = None

        # Validate
        rejection_reason = self._validate_order(order_data)
        if rejection_reason:
            order = models.Order(
                side=order_data["side"],
                market=order_data.get("market", "RTM"),
                quantity_kwh=order_data["quantity_kwh"],
                limit_price_inr=order_data.get("limit_price_inr"),
                status=models.OrderStatus.REJECTED,
                strategy=order_data.get("strategy", "MANUAL"),
                user_id=user_id,
                notes=f"Rejected: {rejection_reason}",
            )
            db.add(order)
            db.commit()
            db.refresh(order)
            logger.warning(f"Order rejected: {rejection_reason}")
            return order

        # Create pending order
        order = models.Order(
            side=order_data["side"],
            market=order_data.get("market", "RTM"),
            quantity_kwh=order_data["quantity_kwh"],
            limit_price_inr=order_data.get("limit_price_inr"),
            status=models.OrderStatus.PENDING,
            strategy=order_data.get("strategy", "MANUAL"),
            user_id=user_id,
            notes=order_data.get("notes"),
        )
        db.add(order)
        db.commit()
        db.refresh(order)

        # Audit log
        self._log_audit(db, "ORDER_CREATED", {
            "order_id": order.id,
            "side": order_data["side"],
            "qty": order_data["quantity_kwh"],
            "limit_price": order_data.get("limit_price_inr"),
        }, user_id)

        logger.info(f"Order created: #{order.id} {order.side} {order.quantity_kwh} kWh")
        return order

    def _validate_order(self, order_data: dict) -> Optional[str]:
        """Validate an order, return rejection reason or None if valid."""
        qty = order_data["quantity_kwh"]
        side = order_data["side"]

        if self._trading_halted:
            return f"Trading halted: {self._halt_reason}"

        if qty <= 0:
            return "Quantity must be positive"

        if qty > MAX_ORDER_SIZE_KWH:
            return f"Quantity {qty} exceeds max order size {MAX_ORDER_SIZE_KWH} kWh"

        # Check SOC limits
        if side == "SELL" or side == models.OrderSide.SELL:
            available = self._soc - 0.2 * BATTERY_ENERGY
            if qty > available + 1e-6:
                return f"Insufficient SOC: available={available:.1f} kWh, requested={qty:.1f} kWh"

        if side == "BUY" or side == models.OrderSide.BUY:
            headroom = BATTERY_ENERGY - self._soc
            if qty > headroom + 1e-6:
                return f"Battery full: headroom={headroom:.1f} kWh, requested={qty:.1f} kWh"

        return None

    # ══════════════════════════════════════════════════════════
    #  ORDER EXECUTION (FILL)
    # ══════════════════════════════════════════════════════════

    def execute_order(self, db: Session, order: models.Order, market_price: float) -> Optional[models.Trade]:
        """
        Execute (fill) an order at the given market price.
        Returns the Trade object or None if execution fails.
        """
        if order.status not in (models.OrderStatus.PENDING, models.OrderStatus.PARTIAL):
            logger.warning(f"Cannot execute order #{order.id}: status={order.status}")
            return None

        # Check limit price
        if order.limit_price_inr is not None:
            if order.side == models.OrderSide.BUY and market_price > order.limit_price_inr:
                return None  # Price too high for buy limit
            if order.side == models.OrderSide.SELL and market_price < order.limit_price_inr:
                return None  # Price too low for sell limit

        remaining_qty = order.quantity_kwh - order.filled_quantity_kwh
        fill_qty = remaining_qty  # Fill entire remaining

        # Compute fees (0.1% of trade value — typical exchange fee)
        trade_value = fill_qty * market_price
        fees = trade_value * 0.001

        # Net amount: positive for SELL (revenue), negative for BUY (cost)
        if order.side == models.OrderSide.SELL:
            net_amount = trade_value - fees
        else:
            net_amount = -(trade_value + fees)

        # Create trade record
        trade = models.Trade(
            order_id=order.id,
            side=order.side,
            market=order.market,
            quantity_kwh=fill_qty,
            price_inr=market_price,
            fees_inr=fees,
            net_amount_inr=net_amount,
        )
        db.add(trade)

        # Update order
        order.filled_quantity_kwh += fill_qty
        order.filled_avg_price = market_price  # Simplified for single fill
        order.status = models.OrderStatus.FILLED
        order.updated_at = datetime.utcnow()

        # Update position
        self._update_position(order.side, fill_qty, market_price, fees)

        # Save position snapshot
        position = models.Position(
            soc_kwh=self._soc,
            total_bought_kwh=self._total_bought_kwh,
            total_sold_kwh=self._total_sold_kwh,
            total_bought_value_inr=self._total_bought_value,
            total_sold_value_inr=self._total_sold_value,
            realized_pnl_inr=self._realized_pnl,
            degradation_cost_inr=self._degradation_cost,
        )
        db.add(position)

        db.commit()
        db.refresh(trade)

        # Check daily loss limit
        if self._daily_pnl < -DAILY_LOSS_LIMIT_INR:
            self._trading_halted = True
            self._halt_reason = f"Daily loss limit exceeded: ₹{abs(self._daily_pnl):.2f}"
            logger.warning(self._halt_reason)

        # Audit
        self._log_audit(db, "TRADE_EXECUTED", {
            "trade_id": trade.id,
            "order_id": order.id,
            "side": str(order.side),
            "qty": fill_qty,
            "price": market_price,
            "net": net_amount,
            "soc": self._soc,
        })

        logger.info(
            f"Trade filled: #{trade.id} {order.side} {fill_qty:.1f} kWh @ ₹{market_price:.4f} "
            f"| Net: ₹{net_amount:.2f} | SOC: {self._soc:.0f} kWh"
        )
        return trade

    def _update_position(self, side, qty: float, price: float, fees: float):
        """Update running position state after a trade fill."""
        from src.config import ETA

        trade_value = qty * price
        degradation = DEGR_COST * qty
        self._degradation_cost += degradation

        if side == models.OrderSide.BUY or side == "BUY":
            # Charging: add energy to battery (with efficiency loss)
            energy_stored = qty * ETA
            self._soc = min(BATTERY_ENERGY, self._soc + energy_stored)
            self._total_bought_kwh += qty
            self._total_bought_value += trade_value + fees
            profit = -(trade_value + fees + degradation)
        else:
            # Discharging: remove energy from battery (with efficiency loss)
            energy_removed = qty / ETA
            self._soc = max(0.2 * BATTERY_ENERGY, self._soc - energy_removed)
            self._total_sold_kwh += qty
            self._total_sold_value += trade_value - fees
            profit = trade_value - fees - degradation

        self._realized_pnl += profit
        self._daily_pnl += profit

    # ══════════════════════════════════════════════════════════
    #  ORDER CANCELLATION
    # ══════════════════════════════════════════════════════════

    def cancel_order(self, db: Session, order_id: int, user_id: Optional[int] = None) -> Optional[models.Order]:
        """Cancel a pending order."""
        order = db.query(models.Order).filter(models.Order.id == order_id).first()
        if not order:
            return None
        if order.status != models.OrderStatus.PENDING:
            return order  # Already filled/cancelled

        order.status = models.OrderStatus.CANCELLED
        order.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(order)

        self._log_audit(db, "ORDER_CANCELLED", {"order_id": order_id}, user_id)
        logger.info(f"Order cancelled: #{order_id}")
        return order

    # ══════════════════════════════════════════════════════════
    #  POSITION QUERIES
    # ══════════════════════════════════════════════════════════

    def get_position(self, current_price: float = 0.0) -> dict:
        """Get current position state."""
        avg_buy = (self._total_bought_value / self._total_bought_kwh) if self._total_bought_kwh > 0 else 0.0
        avg_sell = (self._total_sold_value / self._total_sold_kwh) if self._total_sold_kwh > 0 else 0.0

        # Unrealized P&L: value of current SOC at market price minus cost basis
        stored_energy = self._soc - 0.2 * BATTERY_ENERGY
        unrealized = stored_energy * current_price if stored_energy > 0 else 0.0

        return {
            "soc_kwh": round(self._soc, 1),
            "soc_pct": round(self._soc / BATTERY_ENERGY * 100, 1),
            "total_bought_kwh": round(self._total_bought_kwh, 1),
            "total_sold_kwh": round(self._total_sold_kwh, 1),
            "total_bought_value_inr": round(self._total_bought_value, 2),
            "total_sold_value_inr": round(self._total_sold_value, 2),
            "realized_pnl_inr": round(self._realized_pnl, 2),
            "unrealized_pnl_inr": round(unrealized, 2),
            "total_pnl_inr": round(self._realized_pnl + unrealized, 2),
            "degradation_cost_inr": round(self._degradation_cost, 2),
            "avg_buy_price": round(avg_buy, 4),
            "avg_sell_price": round(avg_sell, 4),
        }

    def get_risk_status(self) -> dict:
        """Get current risk limit status."""
        return {
            "max_order_size_kwh": MAX_ORDER_SIZE_KWH,
            "daily_loss_limit_inr": DAILY_LOSS_LIMIT_INR,
            "max_position_kwh": MAX_POSITION_KWH,
            "current_daily_pnl": round(self._daily_pnl, 2),
            "current_position_kwh": round(self._soc, 1),
            "loss_limit_utilization_pct": round(
                min(100, abs(self._daily_pnl) / DAILY_LOSS_LIMIT_INR * 100), 1
            ) if DAILY_LOSS_LIMIT_INR > 0 else 0.0,
            "position_utilization_pct": round(self._soc / MAX_POSITION_KWH * 100, 1),
            "is_trading_halted": self._trading_halted,
            "halt_reason": self._halt_reason,
        }

    # ══════════════════════════════════════════════════════════
    #  HELPERS
    # ══════════════════════════════════════════════════════════

    def _log_audit(self, db: Session, action: str, details: dict, user_id: Optional[int] = None):
        """Write an audit log entry."""
        log = models.AuditLog(
            action=action,
            details=json.dumps(details, default=str),
            user_id=user_id,
        )
        db.add(log)
        db.commit()

    def get_pending_orders(self, db: Session) -> List[models.Order]:
        """Get all pending orders."""
        return db.query(models.Order).filter(
            models.Order.status == models.OrderStatus.PENDING
        ).order_by(models.Order.created_at).all()

    @property
    def soc(self) -> float:
        return self._soc

    @property
    def is_halted(self) -> bool:
        return self._trading_halted
