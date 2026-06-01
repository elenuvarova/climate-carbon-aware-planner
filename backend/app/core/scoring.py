"""4-axis scoring engine: carbon · price · weather · (comfort as hard gate)."""
import numpy as np
import pandas as pd


# ── normalisation helpers ────────────────────────────────────────────────────

def _norm(series: pd.Series, lower_is_better: bool = True) -> pd.Series:
    """Normalise to 0-100 across the window. higher score = better slot."""
    mn, mx = series.min(), series.max()
    if mx == mn:
        return pd.Series(50.0, index=series.index)
    raw = (mx - series) / (mx - mn) if lower_is_better else (series - mn) / (mx - mn)
    return (raw * 100).clip(0, 100)


# ── weather sub-scores (per slot) ────────────────────────────────────────────

def _drying_score(row: pd.Series) -> float:
    """Suitability for outdoor laundry drying (0-100). Returns 0 if it's raining."""
    if row.get("precipitation", 0.0) > 0.1:
        return 0.0  # hard gate: raining → invalid slot

    precip_s = max(0.0, 100.0 - float(row.get("precipitation_probability", 0.0)))

    hum = float(row.get("relative_humidity_2m", 70.0))
    hum_s = float(np.clip(100.0 * (90.0 - hum) / 50.0, 0, 100))  # 40 → 100, 90 → 0

    wind = float(row.get("wind_speed_10m", 10.0))
    if wind < 3:
        wind_s = 40.0
    elif wind <= 20:
        wind_s = 40.0 + 60.0 * (wind - 3) / 17
    elif wind <= 40:
        wind_s = 100.0 - 50.0 * (wind - 20) / 20
    else:
        wind_s = max(0.0, 50.0 - 50.0 * (wind - 40) / 20)

    rad = float(row.get("shortwave_radiation", 0.0))
    rad_s = float(np.clip(100.0 * rad / 250.0, 0, 100))

    return 0.35 * precip_s + 0.30 * hum_s + 0.20 * wind_s + 0.15 * rad_s


def _ventilation_score(row: pd.Series) -> float:
    """Suitability for opening windows (0-100)."""
    precip_s = max(0.0, 100.0 - float(row.get("precipitation_probability", 0.0)) * 2)

    temp = float(row.get("temperature_2m", 18.0))
    if 10 <= temp <= 25:
        temp_s = 100.0
    elif temp < 5 or temp > 32:
        temp_s = 20.0
    elif temp < 10:
        temp_s = 100.0 * (temp - 5) / 5
    else:
        temp_s = 100.0 * (32 - temp) / 7

    wind = float(row.get("wind_speed_10m", 8.0))
    wind_s = float(np.clip(100.0 - max(0, wind - 15) * 3, 20, 100))

    hum = float(row.get("relative_humidity_2m", 60.0))
    hum_s = float(np.clip(100.0 - max(0, hum - 65) * 2, 0, 100))

    return 0.40 * precip_s + 0.30 * temp_s + 0.20 * wind_s + 0.10 * hum_s


# ── per-slot weather scores for the whole grid ───────────────────────────────

WEATHER_SCORERS = {
    "drying": _drying_score,
    "ventilation": _ventilation_score,
}


def add_weather_scores(df: pd.DataFrame) -> pd.DataFrame:
    """Add weather_score_drying and weather_score_ventilation columns to the slot grid."""
    weather_cols = {"temperature_2m", "relative_humidity_2m", "precipitation_probability",
                    "precipitation", "wind_speed_10m", "shortwave_radiation"}
    has_weather = weather_cols.issubset(df.columns)

    if has_weather:
        df["weather_score_drying"] = df.apply(_drying_score, axis=1)
        df["weather_score_ventilation"] = df.apply(_ventilation_score, axis=1)
    else:
        df["weather_score_drying"] = np.nan
        df["weather_score_ventilation"] = np.nan

    return df


# ── global carbon / price scores ────────────────────────────────────────────

def add_global_scores(df: pd.DataFrame) -> pd.DataFrame:
    """Add carbon_score and price_score columns (0-100, normalised across the window)."""
    df["carbon_score"] = _norm(df["ci_gco2"], lower_is_better=True)

    if "price_p" in df.columns and df["price_p"].notna().any():
        df["price_score"] = _norm(df["price_p"], lower_is_better=True)
    else:
        df["price_score"] = np.nan

    return df


# ── task fit score ────────────────────────────────────────────────────────────

def task_fit_scores(
    df: pd.DataFrame,
    weather_profile: str | None,
    mode: str,
) -> pd.Series:
    """
    Compute a single composite fit score (0-100) per slot for a given task.
    Returns a Series aligned to df.index.
    """
    from app.core.tasks import MODE_WEIGHTS, MODE_WEIGHTS_NO_WEATHER

    has_price = df["price_score"].notna().any()
    weather_col = f"weather_score_{weather_profile}" if weather_profile else None
    has_weather = weather_col is not None and weather_col in df.columns and df[weather_col].notna().any()

    carbon = df["carbon_score"].fillna(50.0)
    price = df["price_score"].fillna(50.0) if has_price else pd.Series(np.nan, index=df.index)

    if has_weather and has_price:
        w = MODE_WEIGHTS.get(mode, MODE_WEIGHTS["balanced"])
        weather_s = df[weather_col].fillna(0.0)
        return w["carbon"] * carbon + w["price"] * price + w["weather"] * weather_s

    if has_weather and not has_price:
        # Redistribute price weight to carbon
        weather_s = df[weather_col].fillna(0.0)
        wc = 0.70 if mode == "green" else (0.30 if mode == "money" else 0.50)
        ww = 1.0 - wc
        return wc * carbon + ww * weather_s

    if not has_weather and has_price:
        w = MODE_WEIGHTS_NO_WEATHER.get(mode, MODE_WEIGHTS_NO_WEATHER["balanced"])
        return w["carbon"] * carbon + w["price"] * price

    # Only carbon available
    return carbon
