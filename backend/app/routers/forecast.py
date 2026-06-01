import math

import pandas as pd
from fastapi import APIRouter

from app.core.scoring import add_global_scores, add_weather_scores
from app.core.slots import build_slot_grid
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


async def build_grid_with_scores(region_id: int = 13):
    """Shared pipeline: fetch all three sources → slot grid → scored DataFrame."""
    carbon = await fetch_carbon(region_id)
    price = await fetch_price()
    weather = await fetch_weather()

    df = build_slot_grid(carbon, price, weather)
    df = add_global_scores(df)
    df = add_weather_scores(df)
    return df


@router.get("/api/forecast", response_model=ForecastResponse)
async def forecast(region_id: int = 13):
    df = await build_grid_with_scores(region_id)
    slots = [row_to_slot(ts, row) for ts, row in df.iterrows()]
    return ForecastResponse(slots=slots, location="London", region_id=region_id)
