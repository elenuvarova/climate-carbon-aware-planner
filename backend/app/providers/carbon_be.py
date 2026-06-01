"""Belgium carbon intensity — modelled estimate via Open-Meteo.

Uses renewable generation proxies (solar radiation + wind speed) together
with the Belgian grid baseline to estimate a 48-h forward CI series.

Belgian grid 2024 characteristics:
  - Average CI: ~165 gCO₂/kWh
  - Nuclear: ~40%, Gas: ~25%, Renewables: ~25%, Imports: ~10%
  - Typical range: 50–200 gCO₂/kWh

This is an approximation — a proper integration would use the Elia open data
API (opendata.elia.be) once a reliable free forecast endpoint is confirmed.
Clearly labelled in the UI as "modelled estimate".
"""
import logging
from datetime import datetime, timezone

import pandas as pd
from cachetools import TTLCache

from app.http_client import client

log = logging.getLogger(__name__)

_cache: TTLCache = TTLCache(maxsize=8, ttl=3600)  # 1-h TTL (model is stable)

BASELINE_GCO2 = 165.0  # gCO₂/kWh, Belgian annual average 2024


def _bucket() -> str:
    now = datetime.now(timezone.utc)
    return now.replace(minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H")


def _estimate_ci(solar_wm2: float, wind_ms: float, hour_utc: int) -> float:
    """Estimate Belgian grid CI from renewable generation proxies."""
    solar_reduction = min(45.0, (solar_wm2 or 0.0) / 150.0)
    wind_reduction = min(65.0, (wind_ms or 0.0) * 4.0)

    # Local CET/CEST ≈ UTC+1 (winter) / UTC+2 (summer) — rough approximation
    local_hour = (hour_utc + 1) % 24
    is_morning_peak = 7 <= local_hour < 10
    is_evening_peak = 16 <= local_hour < 20
    demand_bump = 25.0 if (is_morning_peak or is_evening_peak) else 0.0
    night_discount = -20.0 if local_hour < 6 else 0.0

    return max(45.0, BASELINE_GCO2 - solar_reduction - wind_reduction + demand_bump + night_discount)


async def fetch_carbon_be(lat: float = 51.2194, lon: float = 4.4025) -> pd.Series:
    """
    Returns a pd.Series of estimated gCO₂/kWh indexed by UTC slot-start
    (30-min resolution, ~48 h), derived from Open-Meteo solar + wind forecast.
    """
    key = f"carbon_be:{_bucket()}"
    if key in _cache:
        return _cache[key]

    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "shortwave_radiation,wind_speed_10m",
        "forecast_days": 3,
        "timezone": "UTC",
    }

    try:
        r = await client().get("https://api.open-meteo.com/v1/forecast", params=params)
        r.raise_for_status()
        hourly = r.json()["hourly"]

        times = pd.to_datetime(hourly["time"], utc=True)
        solar = hourly.get("shortwave_radiation") or [0.0] * len(times)
        wind = hourly.get("wind_speed_10m") or [0.0] * len(times)

        values = [
            _estimate_ci(solar[i], wind[i], int(ts.hour))
            for i, ts in enumerate(times)
        ]

        hourly_series = pd.Series(data=values, index=times)
        # Interpolate to 30-min resolution
        series = hourly_series.resample("30min").interpolate(method="linear")

        # Trim to 48 h from now
        now_utc = pd.Timestamp.now(tz="UTC").floor("30min")
        series = series[series.index >= now_utc].iloc[:96]

        _cache[key] = series
        return series

    except Exception as exc:
        log.error("Belgium carbon model (Open-Meteo) failed: %s", exc)
        raise


async def fetch_carbon_be_7d(lat: float = 51.2194, lon: float = 4.4025) -> pd.Series:
    """7-day carbon series (336 slots) from Open-Meteo 7-day weather forecast."""
    key = f"carbon_be_7d:{_bucket()}"
    if key in _cache:
        return _cache[key]

    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "shortwave_radiation,wind_speed_10m",
        "forecast_days": 8,
        "timezone": "UTC",
    }

    try:
        r = await client().get("https://api.open-meteo.com/v1/forecast", params=params)
        r.raise_for_status()
        hourly = r.json()["hourly"]

        times = pd.to_datetime(hourly["time"], utc=True)
        solar = hourly.get("shortwave_radiation") or [0.0] * len(times)
        wind = hourly.get("wind_speed_10m") or [0.0] * len(times)

        values = [
            _estimate_ci(solar[i], wind[i], int(ts.hour))
            for i, ts in enumerate(times)
        ]

        hourly_series = pd.Series(data=values, index=times)
        series = hourly_series.resample("30min").interpolate(method="linear")

        now_utc = pd.Timestamp.now(tz="UTC").floor("30min")
        series = series[series.index >= now_utc].iloc[:336]

        _cache[key] = series
        return series

    except Exception as exc:
        log.error("Belgium 7d carbon model (Open-Meteo) failed: %s", exc)
        raise
