from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.core.tasks import TEMPLATES

# "HH:MM" 24-hour time, 00:00–23:59
_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_TASK_TYPES = set(TEMPLATES)
City = Literal["london", "paris", "antwerp"]
Mode = Literal["green", "money", "balanced"]


def _check_hhmm(v: str) -> str:
    if not _HHMM.match(v):
        raise ValueError(f"expected HH:MM (00:00–23:59), got {v!r}")
    return v


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
    duration_mins: int = Field(ge=30, le=1440)  # one 30-min slot … 24 h
    window_start: str   # "HH:MM" — daily availability start, local city time
    window_end: str     # "HH:MM" — daily availability end, local city time
    deadline: str | None = None  # "HH:MM" — must finish by (next occurrence)

    @field_validator("type")
    @classmethod
    def _known_type(cls, v: str) -> str:
        if v not in _TASK_TYPES:
            raise ValueError(f"unknown task type {v!r}; expected one of {sorted(_TASK_TYPES)}")
        return v

    @field_validator("window_start", "window_end")
    @classmethod
    def _valid_window(cls, v: str) -> str:
        return _check_hhmm(v)

    @field_validator("deadline")
    @classmethod
    def _valid_deadline(cls, v: str | None) -> str | None:
        return _check_hhmm(v) if v is not None else v


class PlanRequest(BaseModel):
    location: str = "London"
    city: City = "london"
    region_id: int = 13           # legacy: ignored when city != "london"
    mode: Mode = "balanced"
    tasks: list[TaskIn] = Field(min_length=1, max_length=20)


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
    plan_id: int | None = None


# ── History ───────────────────────────────────────────────────────────────────

class PlanHistoryItem(BaseModel):
    id: int
    created_at: str
    location: str
    mode: str
    city: str = ""
    recommendations: list[RecommendationOut]


class PlansResponse(BaseModel):
    plans: list[PlanHistoryItem]


# ── Feedback ──────────────────────────────────────────────────────────────────

class FeedbackIn(BaseModel):
    plan_id: int = Field(ge=1)
    task_type: str = Field(min_length=1, max_length=64)
    followed: bool | None = None
    rating: int | None = Field(default=None, ge=1, le=5)


# ── Compare (all 3 modes in one call) ─────────────────────────────────────────

class CompareRequest(BaseModel):
    location: str = "London"
    city: City = "london"
    tasks: list[TaskIn] = Field(min_length=1, max_length=20)


class CompareResponse(BaseModel):
    location: str
    city: str
    carbon_label: str
    slots: list[SlotOut]
    modes: dict[str, list[RecommendationOut]]  # "balanced" | "green" | "money" → recs


# ── Weekly brief ──────────────────────────────────────────────────────────────

class WeeklyTaskRec(BaseModel):
    task_type: str
    task_label: str
    best_start: str | None = None   # ISO-8601 UTC; None = no valid window that day
    best_end: str | None = None
    score: float                    # 0-100 composite fit score


class DayBrief(BaseModel):
    date: str               # "YYYY-MM-DD" in city local timezone
    day_label: str          # "Monday 2 Jun"
    avg_carbon_score: float # 0-100 average across all slots that day
    tasks: list[WeeklyTaskRec]


class WeeklyRequest(BaseModel):
    city: City = "london"
    tasks: list[TaskIn] = Field(min_length=1, max_length=20)


class WeeklyResponse(BaseModel):
    location: str
    city: str
    carbon_label: str
    days: list[DayBrief]
    brief: str              # natural language text from Groq (or template fallback)
