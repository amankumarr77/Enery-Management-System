import pulp
from src.config import (
    BATTERY_POWER, BATTERY_ENERGY, ETA, DEGR_COST, DEV_PENALTY,
    HORIZON, SCENARIOS, ALPHA, LAMBDA,
)


def optimize_battery(forecast_prices, scenario_prices, soc_current):
    """
    CVaR-based stochastic battery dispatch optimisation.

    Parameters
    ----------
    forecast_prices : array-like, shape (HORIZON,)
        Point-forecast DAM prices for the planning window.
    scenario_prices : list of array-like, each shape (HORIZON,)
        SCENARIOS realisations of RTM prices (forecast + noise).
    soc_current : float
        Current state-of-charge in kWh.

    Returns
    -------
    q_dispatch : float
        Optimal net power for the first time-step (kW).
        Positive = discharge/sell, Negative = charge/buy.
    """
    S = len(scenario_prices)
    T = HORIZON

    prob = pulp.LpProblem("Battery_CVaR", pulp.LpMaximize)

    # ── Decision variables ──────────────────────────────────────
    # Net power per hour (positive = discharge, negative = charge)
    q = pulp.LpVariable.dicts("q", range(T),
                              lowBound=-BATTERY_POWER,
                              upBound=BATTERY_POWER)

    # Decomposed into charge (q_neg) and discharge (q_pos) components
    q_pos = pulp.LpVariable.dicts("q_pos", range(T), lowBound=0, upBound=BATTERY_POWER)
    q_neg = pulp.LpVariable.dicts("q_neg", range(T), lowBound=0, upBound=BATTERY_POWER)

    # State of charge
    soc = pulp.LpVariable.dicts("soc", range(T),
                                lowBound=0.2 * BATTERY_ENERGY,   # 20% min SOC (depth-of-discharge limit)
                                upBound=BATTERY_ENERGY)

    # Per-scenario profit
    profit_s = pulp.LpVariable.dicts("profit", range(S))

    # CVaR auxiliary variables
    eta_var = pulp.LpVariable("VaR")                                # Value-at-Risk
    xi = pulp.LpVariable.dicts("xi", range(S), lowBound=0)          # Shortfall beyond VaR

    # ── Objective: (1-λ)·E[profit] + λ·CVaR ────────────────────
    expected_profit = pulp.lpSum(profit_s[s] for s in range(S)) / S

    cvar_term = eta_var - (1.0 / ((1.0 - ALPHA) * S)) * pulp.lpSum(xi[s] for s in range(S))

    prob += (1 - LAMBDA) * expected_profit + LAMBDA * cvar_term

    # ── Battery physics constraints ─────────────────────────────
    for t in range(T):
        prev_soc = soc[t - 1] if t > 0 else soc_current
        # SOC transition: charge adds energy (with loss), discharge removes energy (with loss)
        prob += soc[t] == prev_soc + ETA * q_neg[t] - q_pos[t] / ETA
        # Link net power to decomposition
        prob += q[t] == q_pos[t] - q_neg[t]

    # ── Scenario profit constraints ─────────────────────────────
    for s in range(S):
        prob += profit_s[s] == pulp.lpSum(
            q[t] * scenario_prices[s][t]
            - DEV_PENALTY * (q_pos[t] + q_neg[t])
            - DEGR_COST * (q_pos[t] + q_neg[t])
            for t in range(T)
        )

    # ── CVaR constraints ────────────────────────────────────────
    for s in range(S):
        prob += xi[s] >= eta_var - profit_s[s]

    # ── Solve ───────────────────────────────────────────────────
    status = prob.solve(pulp.PULP_CBC_CMD(msg=False))
    if status != pulp.constants.LpStatusOptimal:
        import logging
        logging.warning(f"Solver status: {pulp.LpStatus[status]}")

    return pulp.value(q[0])
