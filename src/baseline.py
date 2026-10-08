import numpy as np
import pandas as pd
from src.config import BATTERY_POWER, BATTERY_ENERGY, ETA, DEGR_COST, DEV_PENALTY


def naive_strategy(df):
    """
    Naive peak/off-peak strategy:
    - Identify the 4 cheapest hours of each day → charge at max power
    - Identify the 4 most expensive hours of each day → discharge at max power
    - Idle otherwise

    Returns a DataFrame with the same schema as simulation output, including
    revenue breakdown columns.
    """
    results = []
    soc = 0.2 * BATTERY_ENERGY  # Start at min SOC like optimizer

    df = df.copy()
    df["date"] = df["Timestamp"].dt.date

    for date, group in df.groupby("date"):
        sorted_hours = group.sort_values("Price_INR_kWh")
        cheap_indices = sorted_hours.head(4).index.tolist()
        expensive_indices = sorted_hours.tail(4).index.tolist()

        for idx in group.index:
            row = df.loc[idx]
            price = row["Price_INR_kWh"]

            if idx in cheap_indices and soc < BATTERY_ENERGY:
                # Charge
                q_charge = min(BATTERY_POWER, (BATTERY_ENERGY - soc) / ETA)
                q = -q_charge  # Negative = buying/charging
                soc_next = soc + ETA * q_charge
            elif idx in expensive_indices and soc > 0.2 * BATTERY_ENERGY:
                # Discharge
                q_discharge = min(BATTERY_POWER, (soc - 0.2 * BATTERY_ENERGY) * ETA)
                q = q_discharge  # Positive = selling/discharging
                soc_next = soc - q_discharge / ETA
            else:
                q = 0.0
                soc_next = soc

            soc_next = max(0.2 * BATTERY_ENERGY, min(BATTERY_ENERGY, soc_next))

            abs_power = abs(q)
            energy_revenue = q * price
            degradation_cost = DEGR_COST * abs_power
            deviation_penalty = DEV_PENALTY * abs_power
            profit = energy_revenue - degradation_cost - deviation_penalty

            results.append({
                "Timestamp": row["Timestamp"],
                "Price": price,
                "Forecast_Price": price,  # Naive uses actual prices
                "Battery_Power": q,
                "SOC": soc,
                "Profit": profit,
                "Energy_Revenue": energy_revenue,
                "Degradation_Cost": degradation_cost,
                "Deviation_Penalty": deviation_penalty,
            })
            soc = soc_next

    return pd.DataFrame(results)


def no_storage_baseline(df):
    """
    No-storage baseline — battery is never used.
    Profit is always zero; useful as a floor reference.
    """
    results = []
    for idx in range(len(df)):
        row = df.iloc[idx]
        results.append({
            "Timestamp": row["Timestamp"],
            "Price": row["Price_INR_kWh"],
            "Forecast_Price": row["Price_INR_kWh"],
            "Battery_Power": 0.0,
            "SOC": 0.0,
            "Profit": 0.0,
            "Energy_Revenue": 0.0,
            "Degradation_Cost": 0.0,
            "Deviation_Penalty": 0.0,
        })
    return pd.DataFrame(results)
