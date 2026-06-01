from __future__ import annotations

from pydantic import BaseModel


class SlotOut(BaseModel):
    start: str          # ISO-8601 UTC
    ci_gco2: float
    price_p: float | None = None
    temp: float | None = None
    humidity: float | None = None
    precip_prob: float | None = None
    wind_speed: float | None = None
    radiation: float | None = None
    carbon_score: float
    price_score: float | None = None
    weather_score_drying: float | None = None
    weather_score_ventilation: float | None = None


class ForecastResponse(BaseModel):
    slots: list[SlotOut]
    location: str
    city: str = "london"
    carbon_label: str = ""
    region_id: int = 13  # kept for backward compat


class TaskIn(BaseModel):
    type: str           # laundry_airdry | laundry_dryer | dishwasher | ev_charge | ventilation
    duration_mins: int
    window_start: str   # "HH:MM" — daily availability start, local city time
    window_end: str     # "HH:MM" — daily availability end, local city time
    deadline: str | None = None  # "HH:MM" — must finish by (next occurrence)


class PlanRequest(BaseModel):
    location: str = "London"
    city: str = "london"          # "london" | "paris" | "antwerp"
    region_id: int = 13           # legacy: ignored when city != "london"
    mode: str = "balanced"        # green | money | balanced
    tasks: list[TaskIn]


class RecommendationOut(BaseModel):
    task_type: str
    task_label: str
    duration_mins: int
    primary_start: str          # ISO-8601 UTC
    primary_end: str
    backup_start: str | None = None
    backup_end: str | None = None
    carbon_saved_kg: float
    cost_saved_gbp: float
    score: float
    reason: str


class PlanResponse(BaseModel):
    recommendations: list[RecommendationOut]
    slots: list[SlotOut]
    mode: str
    location: str
    city: str = "london"
    carbon_label: str = ""


# ── Compare (all 3 modes in one call) ─────────────────────────────────────────

class CompareRequest(BaseModel):
    location: str = "London"
    city: str = "london"
    tasks: list[TaskIn]


class CompareResponse(BaseModel):
    location: str
    city: str
    carbon_label: str
    slots: list[SlotOut]
    modes: dict[str, list[RecommendationOut]]  # "balanced" | "green" | "money" → recs
