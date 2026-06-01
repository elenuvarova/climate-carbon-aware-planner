"""France carbon intensity via RTE éco2mix / ODRE open data (free, CC-BY, no auth).

Fetches the last ~200 recent records of taux_co2 (real-time national dataset),
then builds a 48-h forward series by matching each future slot to the same
time-of-day from the actuals — a cyclical proxy.

France's grid is ~70% nuclear (CI range: 10–100 gCO₂/kWh); intra-day variation
is lower than the UK but the pattern is stable enough for scheduling.
"""
import logging
from datetime import datetime, timezone

import pandas as pd
from cachetools import TTLCache

from app.http_client import client

log = logging.getLogger(__name__)

_cache: TTLCache = TTLCache(maxsize=8, ttl=1800)  # 30-min TTL

BASE = "https://odre.opendatasoft.com/api/explore/v2.1/catalog/datasets/eco2mix-national-tr/records"
PAGE_SIZE = 100


def _bucket() -> str:
    now = datetime.now(timezone.utc)
    m = (now.minute // 30) * 30
    return now.replace(minute=m, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M")


async def _fetch_page(offset: int = 0) -> list[dict]:
    params = {
        "select": "date_heure,taux_co2",
        "where": "taux_co2 is not null",
        "order_by": "date_heure desc",
        "limit": PAGE_SIZE,
        "offset": offset,
    }
    r = await client().get(BASE, params=params)
    r.raise_for_status()
    return r.json().get("results", [])


async def fetch_carbon_fr() -> pd.Series:
    """
    Returns a pd.Series of gCO₂/kWh indexed by UTC slot-start (30-min, 96 slots ≈ 48 h).
    Each forward slot is matched to the same time-of-day from recent actuals
    (lag 24h first, then 48h, then mean fallback).
    """
    key = f"carbon_fr:{_bucket()}"
    if key in _cache:
        return _cache[key]

    try:
        page0 = await _fetch_page(0)
        page1 = await _fetch_page(PAGE_SIZE)
        raw = page0 + page1

        if not raw:
            raise ValueError("Empty eco2mix RT response")

        index = pd.to_datetime([r["date_heure"] for r in raw], utc=True)
        values = [float(r["taux_co2"]) for r in raw]

        actuals = pd.Series(data=values, index=index).sort_index()
        # Resample 15-min → 30-min
        actuals = actuals.resample("30min").mean().dropna()
        mean_ci = float(actuals.mean())

        # Build 96-slot (48h) forward series using time-of-day cyclical proxy
        now_utc = pd.Timestamp.now(tz="UTC").floor("30min")
        forward_index = pd.date_range(start=now_utc, periods=96, freq="30min")

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

        series = pd.Series(data=forward_values, index=forward_index)
        _cache[key] = series
        return series

    except Exception as exc:
        log.error("France carbon (ODRE RT) failed: %s", exc)
        raise


async def fetch_carbon_fr_7d() -> pd.Series:
    """7-day forward series (336 slots) via cyclical proxy — same logic, extended horizon."""
    key = f"carbon_fr_7d:{_bucket()}"
    if key in _cache:
        return _cache[key]

    try:
        page0 = await _fetch_page(0)
        page1 = await _fetch_page(PAGE_SIZE)
        raw = page0 + page1

        if not raw:
            raise ValueError("Empty eco2mix RT response")

        index = pd.to_datetime([r["date_heure"] for r in raw], utc=True)
        values = [float(r["taux_co2"]) for r in raw]
        actuals = pd.Series(data=values, index=index).sort_index()
        actuals = actuals.resample("30min").mean().dropna()
        mean_ci = float(actuals.mean())

        now_utc = pd.Timestamp.now(tz="UTC").floor("30min")
        forward_index = pd.date_range(start=now_utc, periods=336, freq="30min")  # 7 days

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

        series = pd.Series(data=forward_values, index=forward_index)
        _cache[key] = series
        return series

    except Exception as exc:
        log.error("France 7d carbon (ODRE RT) failed: %s", exc)
        raise
