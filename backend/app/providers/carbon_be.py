"""Belgium carbon intensity via Elia open data (free, no auth, CC-BY).

Dataset ods191 — Production-Based & Consumption-Based CO₂ Intensity Belgium,
near real-time, updated every hour.

We use the `consumption` field (gCO2eq/kWh) which includes cross-border flows
and is more accurate for household scheduling than production-based intensity.

Belgian grid 2024 characteristics:
  - Nuclear ~40%, Gas ~25%, Renewables ~25%, Imports ~10%
  - Typical consumption-based CI: 80–220 gCO2eq/kWh

Forward 48h/7d series built via cyclical time-of-day proxy — same approach
as the France provider — since Elia publishes actuals, not forecasts.
"""
import logging
from datetime import datetime, timezone

import pandas as pd
from cachetools import TTLCache

from app.http_client import client

log = logging.getLogger(__name__)

_cache: TTLCache = TTLCache(maxsize=8, ttl=1800)  # 30-min TTL

BASE = "https://opendata.elia.be/api/explore/v2.1/catalog/datasets/ods192/records"
PAGE_SIZE = 100


def _bucket() -> str:
    now = datetime.now(timezone.utc)
    m = (now.minute // 30) * 30
    return now.replace(minute=m, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M")


async def _fetch_page(offset: int = 0) -> list[dict]:
    params = {
        "select": "datetime,consumption",
        "where": "consumption is not null",
        "order_by": "datetime desc",
        "limit": PAGE_SIZE,
        "offset": offset,
    }
    r = await client().get(BASE, params=params)
    r.raise_for_status()
    return r.json().get("results", [])


async def _fetch_actuals() -> pd.Series:
    """Fetch last ~200 hourly records and interpolate to 30-min resolution."""
    page0 = await _fetch_page(0)
    page1 = await _fetch_page(PAGE_SIZE)
    raw = page0 + page1

    if not raw:
        raise ValueError("Empty Elia ods191 response")

    index = pd.to_datetime([r["datetime"] for r in raw], utc=True)
    values = [float(r["consumption"]) for r in raw]

    actuals = pd.Series(data=values, index=index).sort_index()
    # Elia publishes hourly; resample → 30-min via linear interpolation
    return actuals.resample("30min").interpolate(method="linear").dropna()


def _build_forward(actuals: pd.Series, periods: int) -> pd.Series:
    """Build a forward series of `periods` slots via cyclical time-of-day proxy."""
    mean_ci = float(actuals.mean())
    now_utc = pd.Timestamp.now(tz="UTC").floor("30min")
    forward_index = pd.date_range(start=now_utc, periods=periods, freq="30min")

    forward_values: list[float] = []
    for ts in forward_index:
        val = mean_ci
        for lag_h in (24, 48, 72):
            ref = ts - pd.Timedelta(hours=lag_h)
            diffs = abs(actuals.index - ref)
            if len(diffs) == 0:
                break
            min_i = int(diffs.argmin())
            if diffs[min_i] < pd.Timedelta(minutes=30):
                val = float(actuals.iloc[min_i])
                break
        forward_values.append(val)

    return pd.Series(data=forward_values, index=forward_index)


async def fetch_carbon_be(lat: float = 51.2194, lon: float = 4.4025) -> pd.Series:
    """
    Returns a pd.Series of gCO2eq/kWh indexed by UTC slot-start
    (30-min resolution, 96 slots ≈ 48 h).
    lat/lon kept for API compatibility; Elia data is national.
    """
    key = f"carbon_be:{_bucket()}"
    if key in _cache:
        return _cache[key]

    try:
        actuals = await _fetch_actuals()
        series = _build_forward(actuals, 96)
        _cache[key] = series
        return series
    except Exception as exc:
        log.error("Belgium carbon (Elia ods191) failed: %s", exc)
        raise


async def fetch_carbon_be_7d(lat: float = 51.2194, lon: float = 4.4025) -> pd.Series:
    """7-day forward series (336 slots) via cyclical proxy from Elia actuals."""
    key = f"carbon_be_7d:{_bucket()}"
    if key in _cache:
        return _cache[key]

    try:
        actuals = await _fetch_actuals()
        series = _build_forward(actuals, 336)
        _cache[key] = series
        return series
    except Exception as exc:
        log.error("Belgium 7d carbon (Elia ods191) failed: %s", exc)
        raise
