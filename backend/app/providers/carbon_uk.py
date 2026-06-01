"""UK Carbon Intensity API — https://carbonintensity.org.uk/ (free, CC-BY, no auth)."""
import logging
from datetime import datetime, timezone

import pandas as pd
from cachetools import TTLCache

from app.http_client import client

log = logging.getLogger(__name__)

_cache: TTLCache = TTLCache(maxsize=32, ttl=1800)  # 30-min TTL

BASE = "https://api.carbonintensity.org.uk"


def _bucket() -> str:
    """Round current time to nearest 30 min — used as cache key component."""
    now = datetime.now(timezone.utc)
    m = (now.minute // 30) * 30
    return now.replace(minute=m, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M")


async def fetch_carbon(region_id: int = 13) -> pd.Series:
    """
    Returns a Series of gCO₂/kWh indexed by UTC slot-start (30-min resolution, ~48 h).
    Falls back to national data if the regional endpoint fails.
    """
    key = f"carbon:{region_id}:{_bucket()}"
    if key in _cache:
        return _cache[key]

    now = datetime.now(timezone.utc)
    from_str = now.strftime("%Y-%m-%dT%H:%MZ")

    try:
        r = await client().get(f"{BASE}/regional/intensity/{from_str}/fw48h/regionid/{region_id}")
        r.raise_for_status()
        raw = r.json()["data"]["data"]
        index = [slot["from"] for slot in raw]
        values = [slot["intensity"]["forecast"] for slot in raw]
    except Exception as exc:
        log.warning("Regional carbon API failed (%s), trying national fallback", exc)
        try:
            r = await client().get(f"{BASE}/intensity/{from_str}/fw48h")
            r.raise_for_status()
            raw = r.json()["data"]
            index = [slot["from"] for slot in raw]
            values = [slot["intensity"]["forecast"] for slot in raw]
        except Exception as exc2:
            log.error("National carbon API also failed: %s", exc2)
            raise

    series = pd.Series(
        data=[float(v) for v in values],
        index=pd.to_datetime(index, utc=True),
    ).sort_index()

    _cache[key] = series
    return series
