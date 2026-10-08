import pandas as pd

def load_price_data(path):
    df = pd.read_csv(path)
    df["Timestamp"] = pd.to_datetime(df["Timestamp"])
    df = df.sort_values("Timestamp").reset_index(drop=True)

    df["hour"] = df["Timestamp"].dt.hour
    df["dow"] = df["Timestamp"].dt.dayofweek

    return df