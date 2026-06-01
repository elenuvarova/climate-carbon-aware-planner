import math

import pandas as pd
from fastapi import APIRouter

from app.core.city_registry import get_city
from app.core.scoring import add_global_scores, add_weather_scores
from app.core.slots import build_slot_grid
from app.providers.carbon_be import fetch_carbon_be
from app.providers.carbon_fr import fetch_carbon_fr
from app.providers.carbon_uk import fetch_carbon
from app.providers.price_octopus import fetch_price
from app.providers.weather_openmeteo import fetch_weather
from app.schemas import ForecastResponse, SlotOut

router = APIRouter()


def _f(v, digits: int = 1) -> float | None:
    """Float or None — converts NaN/pandas NA to None."""
    if v is None:
        return None
    try:
        f = float(v)
        return None if math.isnan(f) else round(f, digits)
    except (TypeError, ValueError):
        return None


def row_to_slot(ts: pd.Timestamp, row: pd.Series) -> SlotOut:
    return SlotOut(
        start=ts.isoformat(),
        ci_gco2=_f(row.get("ci_gco2"), 1),
        price_p=_f(row.get("price_p"), 2),
        temp=_f(row.get("temperature_2m"), 1),
        humidity=_f(row.get("relative_humidity_2m"), 0),
        precip_prob=_f(row.get("precipitation_probability"), 0),
        wind_speed=_f(row.get("wind_speed_10m"), 1),
        radiation=_f(row.get("shortwave_radiation"), 0),
        carbon_score=_f(row.get("carbon_score"), 1),
        price_score=_f(row.get("price_score"), 1),
        weather_score_drying=_f(row.get("weather_score_drying"), 1),
        weather_score_ventilation=_f(row.get("weather_score_ventilation"), 1),
    )


async def build_grid_with_scores(city_id: str = "london"):
    """Shared pipeline: fetch providers → slot grid → scored DataFrame.

    Returns (df, city) so callers have access to timezone and metadata.
    """
    city = get_city(city_id)

    # Carbon — dispatch by provider type
    if city.carbon_provider == "uk":
        carbon = await fetch_carbon(city.region_id or 13)
    elif city.carbon_provider == "fr":
        carbon = await fetch_carbon_fr()
    else:  # "be"
        carbon = await fetch_carbon_be(city.lat, city.lon)

    # Price — Octopus Agile for London; empty series otherwise
    if city.price_provider == "octopus":
        price = await fetch_price()
    else:
        price = pd.Series(dtype=float)

    # Weather — Open-Meteo for city coordinates
    weather = await fetch_weather(city.lat, city.lon)

    df = build_slot_grid(carbon, price, weather)
    df = add_global_scores(df)
    df = add_weather_scores(df)
    return df, city


@router.get("/api/forecast", response_model=ForecastResponse)
async def forecast(city: str = "london"):
    df, city_cfg = await build_grid_with_scores(city)
    slots = [row_to_slot(ts, row) for ts, row in df.iterrows()]
    return ForecastResponse(
        slots=slots,
        location=city_cfg.name,
        city=city,
        carbon_label=city_cfg.carbon_label,
        region_id=city_cfg.region_id or 0,
    )
