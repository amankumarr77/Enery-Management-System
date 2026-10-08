import numpy as np
import pandas as pd
from src.config import BATTERY_ENERGY, CAPEX


def total_profit(df):
    """Sum of all hourly profits."""
    return float(df["Profit"].sum())


def avg_daily_profit(df):
    """Average profit per day."""
    if "Timestamp" in df.columns:
        daily = df.copy()
        daily["date"] = pd.to_datetime(daily["Timestamp"]).dt.date
        daily_totals = daily.groupby("date")["Profit"].sum()
        return float(daily_totals.mean())
    n_days = max(1, len(df) / 24)
    return float(df["Profit"].sum() / n_days)


def total_cycles(df):
    """
    Count equivalent full cycles.
    One full cycle = discharge BATTERY_ENERGY kWh.
    """
    total_discharge = df.loc[df["Battery_Power"] > 0, "Battery_Power"].sum()
    return float(total_discharge / BATTERY_ENERGY) if BATTERY_ENERGY > 0 else 0.0


def profit_per_cycle(df):
    """Profit earned per full equivalent cycle."""
    cycles = total_cycles(df)
    if cycles == 0:
        return 0.0
    return float(df["Profit"].sum() / cycles)


def max_drawdown(df):
    """
    Maximum peak-to-trough drop in cumulative profit.
    Returns a positive number representing the worst loss streak.
    """
    cum_profit = df["Profit"].cumsum()
    running_max = cum_profit.cummax()
    drawdowns = running_max - cum_profit
    return float(drawdowns.max())


def sharpe_ratio(df):
    """
    Annualised Sharpe ratio of hourly profits.
    Assumes risk-free rate ≈ 0 for simplicity.
    """
    hourly = df["Profit"]
    if hourly.std() == 0:
        return 0.0
    # Annualise: √8760 hours per year
    return float((hourly.mean() / hourly.std()) * np.sqrt(8760))


def utilization_rate(df):
    """
    Fraction of hours where the battery is actively charging or discharging
    (i.e., abs(Battery_Power) > 0).
    """
    active = (df["Battery_Power"].abs() > 1e-6).sum()
    return float(active / len(df)) if len(df) > 0 else 0.0


def revenue_breakdown(df):
    """
    Total energy revenue, degradation costs, and deviation penalties.
    Returns dict with three float values.
    """
    result = {
        "total_energy_revenue": 0.0,
        "total_degradation_cost": 0.0,
        "total_deviation_penalty": 0.0,
    }
    if "Energy_Revenue" in df.columns:
        result["total_energy_revenue"] = round(float(df["Energy_Revenue"].sum()), 2)
    if "Degradation_Cost" in df.columns:
        result["total_degradation_cost"] = round(float(df["Degradation_Cost"].sum()), 2)
    if "Deviation_Penalty" in df.columns:
        result["total_deviation_penalty"] = round(float(df["Deviation_Penalty"].sum()), 2)
    return result


def forecast_accuracy(df):
    """
    MAE and RMSE between forecast and actual prices.
    Only computed if the DataFrame contains a 'Forecast_Price' column.
    """
    if "Forecast_Price" not in df.columns or "Price" not in df.columns:
        return {"forecast_mae": 0.0, "forecast_rmse": 0.0}
    errors = df["Price"] - df["Forecast_Price"]
    mae = float(np.abs(errors).mean())
    rmse = float(np.sqrt((errors ** 2).mean()))
    return {"forecast_mae": round(mae, 4), "forecast_rmse": round(rmse, 4)}


def payback_period(df):
    """
    Estimated payback period in years based on current run's profitability.
    """
    n_hours = len(df)
    if n_hours == 0:
        return float("inf")
    annual_profit = (df["Profit"].sum() / n_hours) * 8760
    if annual_profit <= 0:
        return float("inf")
    return round(float(CAPEX / annual_profit), 2)


def roi_annual(df):
    """
    Annualised return on investment (%).
    """
    n_hours = len(df)
    if n_hours == 0:
        return 0.0
    annual_profit = (df["Profit"].sum() / n_hours) * 8760
    return round(float((annual_profit / CAPEX) * 100), 2)


def compute_all_metrics(df):
    """Return a dict of all key performance metrics."""
    base = {
        "total_profit": round(total_profit(df), 2),
        "avg_daily_profit": round(avg_daily_profit(df), 2),
        "total_cycles": round(total_cycles(df), 2),
        "profit_per_cycle": round(profit_per_cycle(df), 2),
        "max_drawdown": round(max_drawdown(df), 2),
        "sharpe_ratio": round(sharpe_ratio(df), 4),
        "utilization_rate": round(utilization_rate(df), 4),
        "payback_years": payback_period(df),
        "roi_annual_pct": roi_annual(df),
    }
    base.update(revenue_breakdown(df))
    base.update(forecast_accuracy(df))
    return base
