import numpy as np
import pandas as pd
import logging
from src.config import (
    BATTERY_POWER, BATTERY_ENERGY, ETA, DEGR_COST, DEV_PENALTY,
    LAG, HORIZON, SCENARIOS,
)
from src.optimizer import optimize_battery
from src.forecast import predict_horizon

logger = logging.getLogger(__name__)


def simulate_operation(df, model, residuals, seed=42):
    """
    Receding-horizon simulation of battery dispatch.

    Uses recursive forecasting (no future data leakage) and SOC physics
    aligned with the optimizer constraints.

    Parameters
    ----------
    df : DataFrame
        Must contain columns: Timestamp, Price_INR_kWh, hour, dow
    model : trained sklearn model
    residuals : np.ndarray  (training residuals for scenario noise)
    seed : int  (for reproducible scenario sampling)

    Returns
    -------
    DataFrame with columns:
        Timestamp, Price, Forecast_Price, Battery_Power, SOC, Profit,
        Energy_Revenue, Degradation_Cost, Deviation_Penalty
    """
    rng = np.random.RandomState(seed)
    prices = df["Price_INR_kWh"].values
    results = []

    start_idx = LAG
    end_idx = len(df) - HORIZON

    soc = 0.2 * BATTERY_ENERGY  # Start at minimum SOC (matches optimizer lower bound)

    for t in range(start_idx, end_idx):
        # 1. Recursive forecast (strictly causal — no peeking at future)
        forecast = predict_horizon(model, df, prices, t, HORIZON)

        # 2. Generate stochastic scenarios for RTM prices
        scenarios = []
        for _ in range(SCENARIOS):
            noise = rng.choice(residuals, size=HORIZON, replace=True)
            scenario = forecast + noise
            scenarios.append(scenario)

        # 3. Optimize battery dispatch (only first-step decision used)
        q_opt = optimize_battery(forecast, scenarios, soc)

        # 4. Realised settlement at actual price
        realized_price = prices[t]
        forecast_price = forecast[0]  # What we predicted for this hour

        # 5. Decompose into charge/discharge for physics & cost accounting
        if q_opt >= 0:
            q_discharge = q_opt
            q_charge = 0.0
        else:
            q_discharge = 0.0
            q_charge = -q_opt  # Make positive

        # 6. Revenue breakdown
        energy_revenue = q_opt * realized_price
        degradation_cost = DEGR_COST * (q_discharge + q_charge)
        deviation_penalty = DEV_PENALTY * (q_discharge + q_charge)
        profit = energy_revenue - degradation_cost - deviation_penalty

        # 7. SOC update — ALIGNED with optimizer physics
        #    soc_next = soc + ETA * q_charge - q_discharge / ETA
        soc_next = soc + ETA * q_charge - q_discharge / ETA
        soc_next = max(0.2 * BATTERY_ENERGY, min(BATTERY_ENERGY, soc_next))

        results.append({
            "Timestamp": df["Timestamp"].iloc[t],
            "Price": realized_price,
            "Forecast_Price": forecast_price,
            "Battery_Power": q_opt,
            "SOC": soc,
            "Profit": profit,
            "Energy_Revenue": energy_revenue,
            "Degradation_Cost": degradation_cost,
            "Deviation_Penalty": deviation_penalty,
        })

        soc = soc_next

        if t % 100 == 0:
            cum_profit = sum(r["Profit"] for r in results)
            logger.info(
                f"Step {t}/{end_idx}: Cumulative profit = {cum_profit:.2f} | "
                f"Price={realized_price:.3f}, Forecast={forecast_price:.3f}, "
                f"Power={q_opt:.1f}, SOC={soc:.0f}"
            )

    return pd.DataFrame(results)
