"""Calculate £ + kg CO₂ saved vs the naive evening-peak baseline."""
from datetime import timedelta
from zoneinfo import ZoneInfo

import pandas as pd

from app.core.tasks import DRYER_KWH, TaskTemplate

LONDON = ZoneInfo("Europe/London")
PEAK_HOURS = (17, 20)  # 17:00–20:00 local = typical evening peak


def _peak_averages(df: pd.DataFrame, tz: ZoneInfo = LONDON) -> tuple[float, float]:
    """Average carbon intensity and price during evening-peak slots in the grid."""
    local_hours = df.index.map(lambda dt: dt.astimezone(tz).hour)
    peak_mask = (local_hours >= PEAK_HOURS[0]) & (local_hours < PEAK_HOURS[1])
    peak = df[peak_mask]

    ci_peak = float(peak["ci_gco2"].mean()) if not peak.empty else float(df["ci_gco2"].mean())
    price_peak = (
        float(peak["price_p"].mean())
        if "price_p" in peak.columns and peak["price_p"].notna().any()
        else None
    )
    return ci_peak, price_peak


def compute_savings(
    task: TaskTemplate,
    chosen_start,
    duration_mins: int,
    df: pd.DataFrame,
    tz: ZoneInfo = LONDON,
) -> tuple[float, float]:
    """
    Returns (carbon_saved_kg, cost_saved_gbp) comparing the chosen window
    to the evening-peak baseline.

    For laundry_airdry the dryer avoidance dominates: we add the full dryer
    energy saving on top of the shift saving.
    """
    n = max(1, duration_mins // 30)
    pos = df.index.get_loc(chosen_start) if chosen_start in df.index else 0
    chosen_slots = df.iloc[pos: pos + n]

    ci_chosen = float(chosen_slots["ci_gco2"].mean()) if not chosen_slots.empty else float(df["ci_gco2"].mean())
    ci_peak, price_peak = _peak_averages(df, tz)

    # Carbon saving from shifting the task's own energy draw
    kwh = task.kwh
    co2_shift = kwh * (ci_peak - ci_chosen) / 1000  # kg CO₂

    # Additional carbon saving from avoiding the tumble dryer (air-dry only)
    ci_avg = float(df["ci_gco2"].mean())
    co2_avoided = task.avoided_kwh * ci_avg / 1000  # kg CO₂

    carbon_saved = max(0.0, co2_shift) + co2_avoided

    # Cost saving
    if "price_p" in chosen_slots.columns and chosen_slots["price_p"].notna().any():
        price_chosen = float(chosen_slots["price_p"].mean())
        price_diff = (price_peak or price_chosen) - price_chosen
        cost_shift = kwh * price_diff / 100  # £
        cost_avoided = task.avoided_kwh * (price_peak or 20.0) / 100
    else:
        cost_shift = 0.0
        cost_avoided = 0.0

    cost_saved = max(0.0, cost_shift) + cost_avoided

    return round(carbon_saved, 2), round(cost_saved, 2)


def build_reason(
    task_type: str,
    task_label: str,
    carbon_score: float,
    price_score: float | None,
    weather_score: float | None,
    carbon_saved: float,
    cost_saved: float,
) -> str:
    parts = []

    if carbon_score >= 65:
        parts.append(f"grid is {int(carbon_score)}% cleaner than average")
    elif carbon_score >= 45:
        parts.append("grid is cleaner than peak")

    if price_score is not None and price_score >= 65:
        parts.append("electricity is cheaper than peak")

    if task_type == "laundry_airdry" and weather_score is not None and weather_score >= 55:
        parts.append("dry & breezy — good drying conditions")
    elif task_type == "ventilation" and weather_score is not None and weather_score >= 55:
        parts.append("comfortable outdoor air")

    savings = []
    if carbon_saved >= 0.05:
        savings.append(f"~{carbon_saved:.1f} kg CO₂")
    if cost_saved >= 0.01:
        savings.append(f"~£{cost_saved:.2f}")

    if savings:
        saving_str = " / ".join(savings)
        if task_type == "laundry_airdry":
            parts.append(f"saves {saving_str} by skipping the tumble dryer")
        else:
            parts.append(f"saves {saving_str} vs evening schedule")

    if not parts:
        return "Best available window in the next 48 hours."

    joined = ", ".join(parts) + "."
    return joined[0].upper() + joined[1:]
