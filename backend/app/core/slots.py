"""Normalise all data sources into a single 30-min slot DataFrame."""
import numpy as np
import pandas as pd


def build_slot_grid(
    carbon: pd.Series,
    price: pd.Series | None,
    weather: pd.DataFrame | None,
) -> pd.DataFrame:
    """
    carbon  — gCO₂/kWh, 30-min UTC index (master index)
    price   — p/kWh, 30-min UTC index (optional)
    weather — hourly UTC DataFrame from Open-Meteo (optional)

    Returns a DataFrame indexed by carbon's DatetimeIndex with all data joined.
    """
    df = pd.DataFrame({"ci_gco2": carbon})

    if price is not None and not price.empty:
        df["price_p"] = price.reindex(df.index)
    else:
        df["price_p"] = np.nan

    if weather is not None and not weather.empty:
        # Upsample hourly → 30-min via linear interpolation
        w30 = weather.resample("30min").interpolate(method="linear").reindex(df.index)
        for col in w30.columns:
            df[col] = w30[col]

    return df
