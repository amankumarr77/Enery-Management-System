import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
from src.config import LAG
import logging

logger = logging.getLogger(__name__)


def _build_features(df, prices, idx):
    """Build feature vector for a single time-step."""
    lag_features = list(prices[idx - LAG:idx])
    hour = df["hour"].iloc[idx]
    dow = df["dow"].iloc[idx]
    month = df["Timestamp"].iloc[idx].month
    is_weekend = 1 if dow >= 5 else 0

    # Rolling statistics (computed from the LAG window — no future leakage)
    window = prices[idx - LAG:idx]
    roll_mean_24 = float(np.mean(window))
    roll_std_24 = float(np.std(window))

    return lag_features + [hour, dow, month, is_weekend, roll_mean_24, roll_std_24]


def train_forecast_model(df, train_ratio=0.7):
    """
    Train a RandomForest price forecaster with a proper train/test split.

    Returns
    -------
    model : RandomForestRegressor
        Trained on the first `train_ratio` of the data.
    residuals : np.ndarray
        Residuals computed on the **training set** only (used for scenario generation).
    accuracy : dict
        Out-of-sample MAE, RMSE, and MAPE on the test set.
    train_end_idx : int
        Index where training data ends (for simulation to know where test begins).
    """
    prices = df["Price_INR_kWh"].values
    n = len(prices)
    train_end = int(n * train_ratio)

    # Build feature matrix (only from LAG onwards)
    X, y, indices = [], [], []
    for i in range(LAG, n):
        X.append(_build_features(df, prices, i))
        y.append(prices[i])
        indices.append(i)

    X, y = np.array(X), np.array(y)
    indices = np.array(indices)

    # Split: train on first portion, test on the rest
    train_mask = indices < train_end
    X_train, y_train = X[train_mask], y[train_mask]
    X_test, y_test = X[~train_mask], y[~train_mask]

    model = RandomForestRegressor(n_estimators=200, max_depth=12, random_state=42)
    model.fit(X_train, y_train)

    # Training residuals (for scenario noise generation)
    residuals = y_train - model.predict(X_train)

    # Out-of-sample accuracy
    y_pred_test = model.predict(X_test)
    mae = mean_absolute_error(y_test, y_pred_test)
    rmse = float(np.sqrt(mean_squared_error(y_test, y_pred_test)))
    mape = float(np.mean(np.abs((y_test - y_pred_test) / np.clip(y_test, 1e-6, None))) * 100)

    accuracy = {"mae": round(mae, 4), "rmse": round(rmse, 4), "mape": round(mape, 2)}
    logger.info(f"Forecast accuracy (test set): MAE={mae:.4f}, RMSE={rmse:.4f}, MAPE={mape:.1f}%")

    return model, residuals, accuracy, train_end


def predict_horizon(model, df, prices, t, horizon):
    """
    Recursive multi-step forecast starting at time `t`.

    Uses actual past data and recursively feeds predictions forward
    for the horizon window. No future data is ever used.
    """
    # Work on a mutable copy of the price history up to time t
    price_buffer = list(prices[:t])
    forecasts = []

    for h in range(horizon):
        idx = t + h
        if idx >= len(df):
            # Past end of data — repeat last forecast
            forecasts.append(forecasts[-1] if forecasts else price_buffer[-1])
            continue

        # Build features using the buffer (which includes previous forecasts)
        buf = np.array(price_buffer)
        lag_feats = list(buf[-(LAG):])
        hour = df["hour"].iloc[idx]
        dow = df["dow"].iloc[idx]
        month = df["Timestamp"].iloc[idx].month
        is_weekend = 1 if dow >= 5 else 0
        roll_mean = float(np.mean(buf[-LAG:]))
        roll_std = float(np.std(buf[-LAG:]))

        feat = np.array([lag_feats + [hour, dow, month, is_weekend, roll_mean, roll_std]])
        pred = float(model.predict(feat)[0])
        forecasts.append(pred)
        price_buffer.append(pred)  # Feed prediction back for next step

    return np.array(forecasts)
