"""Octopus Agile price API — free, public, no auth required."""
import logging
from datetime import datetime, timedelta, timezone

import pandas as pd
from cachetools import TTLCache

from app.http_client import client

log = logging.getLogger(__name__)

_cache: TTLCache = TTLCache(maxsize=32, ttl=3600)  # 1-hour TTL
_product_cache: TTLCache = TTLCache(maxsize=8, ttl=86400)  # 24-hour TTL for product discovery

BASE = "https://api.octopus.energy/v1"
# DNO region letter — 'C' = South East England (London / UKPN)
DEFAULT_REGION = "C"


async def _discover_agile_product() -> str | None:
    key = "agile_product"
    if key in _product_cache:
        return _product_cache[key]
    try:
        r = await client().get(f"{BASE}/products/", params={"brand": "OCTOPUS_ENERGY", "is_variable": "true"})
        r.raise_for_status()
        products = r.json().get("results", [])
        agile = [p for p in products if "AGILE" in p.get("code", "").upper() and not p.get("is_prepay", False)]
        if agile:
            code = sorted(agile, key=lambda p: p.get("available_from", ""), reverse=True)[0]["code"]
            _product_cache[key] = code
            log.info("Discovered Agile product: %s", code)
            return code
    except Exception as exc:
        log.warning("Octopus product discovery failed: %s", exc)
    return None


async def fetch_price(region_code: str = DEFAULT_REGION, hours: int = 48) -> pd.Series:
    """
    Returns a Series of p/kWh (inc. VAT) indexed by UTC slot-start (30-min).
    Returns empty Series (graceful degradation) if the API is unavailable.
    """
    key = f"price:{region_code}:{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
    if key in _cache:
        return _cache[key]

    product_code = await _discover_agile_product()
    if not product_code:
        log.warning("No Agile product found — price axis disabled")
        return pd.Series(dtype=float)

    tariff = f"E-1R-{product_code}-{region_code}"
    url = f"{BASE}/products/{product_code}/electricity-tariffs/{tariff}/standard-unit-rates/"
    now = datetime.now(timezone.utc)
    params = {
        "period_from": now.strftime("%Y-%m-%dT%H:%MZ"),
        "period_to": (now + timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%MZ"),
        "page_size": 200,
    }

    try:
        r = await client().get(url, params=params)
        r.raise_for_status()
        results = r.json().get("results", [])
        if not results:
            return pd.Series(dtype=float)

        index = [item["valid_from"] for item in results]
        values = [float(item["value_inc_vat"]) for item in results]
        series = pd.Series(
            data=values,
            index=pd.to_datetime(index, utc=True),
        ).sort_index()

        _cache[key] = series
        return series
    except Exception as exc:
        log.warning("Octopus price API failed: %s — price axis disabled", exc)
        return pd.Series(dtype=float)
