"""Open-Meteo weather API — https://open-meteo.com/ (free, no key, non-commercial)."""
import logging
from datetime import datetime, timezone

import pandas as pd
from cachetools import TTLCache

from app.http_client import client

log = logging.getLogger(__name__)

_cache: TTLCache = TTLCache(maxsize=32, ttl=3600)  # 1-hour TTL

BASE = "https://api.open-meteo.com/v1/forecast"
HOURLY_VARS = ",".join([
    "temperature_2m",
    "relative_humidity_2m",
    "dew_point_2m",
    "precipitation_probability",
    "precipitation",
    "wind_speed_10m",
    "cloud_cover",
    "shortwave_radiation",
    "uv_index",
])

# London
DEFAULT_LAT = 51.5072
DEFAULT_LON = -0.1276


async def fetch_weather(lat: float = DEFAULT_LAT, lon: float = DEFAULT_LON, days: int = 3) -> pd.DataFrame:
    """
    Returns a DataFrame of weather variables at hourly resolution, UTC index.
    Returns empty DataFrame on failure (graceful degradation).
    """
    key = f"weather:{lat:.2f}:{lon:.2f}:{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H')}"
    if key in _cache:
        return _cache[key]

    try:
        r = await client().get(BASE, params={
            "latitude": lat,
            "longitude": lon,
            "hourly": HOURLY_VARS,
            "forecast_days": days,
            "timezone": "UTC",
        })
        r.raise_for_status()
        data = r.json()
        hourly = data["hourly"]
        times = pd.to_datetime(hourly["time"], utc=True)
        df = pd.DataFrame(
            {col: hourly[col] for col in hourly if col != "time"},
            index=times,
        )
        _cache[key] = df
        return df
    except Exception as exc:
        log.warning("Open-Meteo failed: %s — weather axis disabled", exc)
        return pd.DataFrame()
