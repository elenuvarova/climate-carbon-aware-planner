"""Unit tests for the core scoring, scheduling, and savings engine.

All functions under test are pure (no I/O, no network) — they operate on
pandas DataFrames/Series built in-process, so no mocking is needed.
"""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from app.core.savings import build_reason, compute_savings
from app.core.scheduler import _valid_starts, find_windows
from app.core.scoring import (
    _drying_score,
    _norm,
    _ventilation_score,
    add_global_scores,
    add_weather_scores,
    task_fit_scores,
)
from app.core.tasks import TEMPLATES

LONDON = ZoneInfo("Europe/London")
UTC = timezone.utc


# ── fixtures ────────────────────────────────────────────────────────────────


def _make_slots(
    n: int = 96,
    start: str = "2024-06-10 06:00",
    ci_range: tuple[float, float] = (80.0, 250.0),
    price_range: tuple[float, float] = (5.0, 30.0),
) -> pd.DataFrame:
    """Build a minimal 30-min slot grid with carbon + price data."""
    idx = pd.date_range(start=start, periods=n, freq="30min", tz="UTC")
    rng = np.random.default_rng(42)
    ci = rng.uniform(ci_range[0], ci_range[1], size=n)
    price = rng.uniform(price_range[0], price_range[1], size=n)
    return pd.DataFrame({"ci_gco2": ci, "price_p": price}, index=idx)


def _make_weather_slots(n: int = 96) -> pd.DataFrame:
    """Slot grid with carbon + price + typical-summer weather columns."""
    df = _make_slots(n)
    df["temperature_2m"] = 20.0
    df["relative_humidity_2m"] = 55.0
    df["precipitation_probability"] = 5.0
    df["precipitation"] = 0.0
    df["wind_speed_10m"] = 12.0
    df["shortwave_radiation"] = 200.0
    return df


# ── scoring._norm ───────────────────────────────────────────────────────────


def test_norm_lower_is_better():
    s = pd.Series([100.0, 200.0, 300.0])
    result = _norm(s, lower_is_better=True)
    assert result.iloc[0] == pytest.approx(100.0)
    assert result.iloc[-1] == pytest.approx(0.0)


def test_norm_higher_is_better():
    s = pd.Series([0.0, 50.0, 100.0])
    result = _norm(s, lower_is_better=False)
    assert result.iloc[-1] == pytest.approx(100.0)
    assert result.iloc[0] == pytest.approx(0.0)


def test_norm_constant_returns_50():
    s = pd.Series([42.0, 42.0, 42.0])
    result = _norm(s)
    assert (result == 50.0).all()


# ── scoring._drying_score ────────────────────────────────────────────────────


def test_drying_score_rain_is_hard_gate():
    row = pd.Series({
        "precipitation": 0.5,
        "precipitation_probability": 80.0,
        "relative_humidity_2m": 60.0,
        "wind_speed_10m": 15.0,
        "shortwave_radiation": 150.0,
    })
    assert _drying_score(row) == 0.0


def test_drying_score_ideal_conditions():
    row = pd.Series({
        "precipitation": 0.0,
        "precipitation_probability": 0.0,
        "relative_humidity_2m": 40.0,
        "wind_speed_10m": 15.0,
        "shortwave_radiation": 250.0,
    })
    score = _drying_score(row)
    assert score > 80.0


def test_drying_score_high_humidity():
    dry_row = pd.Series({
        "precipitation": 0.0,
        "precipitation_probability": 0.0,
        "relative_humidity_2m": 40.0,
        "wind_speed_10m": 15.0,
        "shortwave_radiation": 200.0,
    })
    humid_row = dry_row.copy()
    humid_row["relative_humidity_2m"] = 90.0
    assert _drying_score(dry_row) > _drying_score(humid_row)


# ── scoring._ventilation_score ───────────────────────────────────────────────


def test_ventilation_score_comfort_band():
    row = pd.Series({
        "precipitation_probability": 0.0,
        "temperature_2m": 18.0,
        "wind_speed_10m": 8.0,
        "relative_humidity_2m": 50.0,
    })
    assert _ventilation_score(row) == pytest.approx(100.0)


def test_ventilation_score_freezing_lower_than_comfort():
    comfort = pd.Series({
        "precipitation_probability": 0.0,
        "temperature_2m": 18.0,
        "wind_speed_10m": 8.0,
        "relative_humidity_2m": 50.0,
    })
    freezing = comfort.copy()
    freezing["temperature_2m"] = 2.0
    assert _ventilation_score(comfort) > _ventilation_score(freezing)


def test_ventilation_score_storm():
    calm = pd.Series({
        "precipitation_probability": 0.0,
        "temperature_2m": 18.0,
        "wind_speed_10m": 8.0,
        "relative_humidity_2m": 50.0,
    })
    storm = calm.copy()
    storm["wind_speed_10m"] = 60.0
    assert _ventilation_score(calm) > _ventilation_score(storm)


# ── scoring.add_global_scores / add_weather_scores ──────────────────────────


def test_add_global_scores_range():
    df = _make_slots(96)
    df = add_global_scores(df)
    assert df["carbon_score"].between(0, 100).all()
    assert df["price_score"].between(0, 100).all()


def test_add_global_scores_no_price():
    df = _make_slots(96)
    df = df.drop(columns=["price_p"])
    df = add_global_scores(df)
    assert df["price_score"].isna().all()


def test_add_weather_scores_columns_created():
    df = _make_weather_slots(48)
    df = add_weather_scores(df)
    assert "weather_score_drying" in df.columns
    assert "weather_score_ventilation" in df.columns
    assert df["weather_score_drying"].between(0, 100).all()


def test_add_weather_scores_missing_columns_are_nan():
    df = _make_slots(48)  # no weather columns
    df = add_weather_scores(df)
    assert df["weather_score_drying"].isna().all()


# ── scoring.task_fit_scores ──────────────────────────────────────────────────


def test_task_fit_scores_returns_correct_length():
    df = _make_weather_slots()
    df = add_global_scores(df)
    df = add_weather_scores(df)
    result = task_fit_scores(df, weather_profile="drying", mode="balanced")
    assert len(result) == len(df)


def test_task_fit_scores_green_higher_carbon_weight():
    """Green mode should give more weight to carbon than money mode."""
    df = _make_weather_slots(96)
    df = add_global_scores(df)
    df = add_weather_scores(df)
    green = task_fit_scores(df, weather_profile=None, mode="green")
    money = task_fit_scores(df, weather_profile=None, mode="money")
    # Slots where carbon score is high should score better in green mode
    high_carbon_mask = df["carbon_score"] > 70
    assert green[high_carbon_mask].mean() > money[high_carbon_mask].mean()


def test_task_fit_scores_no_weather_profile():
    df = _make_weather_slots()
    df = add_global_scores(df)
    df = add_weather_scores(df)
    result = task_fit_scores(df, weather_profile=None, mode="balanced")
    assert result.between(0, 100).all()


# ── scheduler._valid_starts ──────────────────────────────────────────────────


def _make_index(n: int = 96, start: str = "2024-06-10 06:00") -> pd.DatetimeIndex:
    return pd.date_range(start=start, periods=n, freq="30min", tz="UTC")


def test_valid_starts_basic_window():
    idx = _make_index()
    valid = _valid_starts(idx, "10:00", "16:00", 120, None, tz=LONDON)
    for slot in valid:
        local = slot.astimezone(LONDON)
        assert local.hour >= 10


def test_valid_starts_excludes_midnight_overflow():
    idx = _make_index(96, "2024-06-10 20:00")
    # 2-hour task, window 22:00–23:00; task can't fit (23:00 - 22:00 = 1h < 2h)
    valid = _valid_starts(idx, "22:00", "23:00", 120, None, tz=LONDON)
    assert len(valid) == 0


def test_valid_starts_with_abs_deadline():
    idx = _make_index(96, "2024-06-10 22:00")
    dl = datetime(2024, 6, 11, 7, 0, tzinfo=UTC)  # next morning 07:00
    # EV charge: 4h (240 min), window starts 22:00
    valid = _valid_starts(idx, "22:00", "23:59", 240, None, tz=LONDON, abs_deadline=dl)
    # All valid starts should have (start + 4h) <= 07:00 next day
    for slot in valid:
        assert slot + timedelta(hours=4) <= dl


# ── scheduler.find_windows ───────────────────────────────────────────────────


def test_find_windows_returns_primary_and_backup():
    df = _make_slots(96, start="2024-06-10 06:00")
    df = add_global_scores(df)
    df = add_weather_scores(df)
    fit = task_fit_scores(df, weather_profile=None, mode="balanced")
    windows = find_windows(fit, 90, "08:00", "22:00", tz=LONDON)
    assert len(windows) >= 1
    if len(windows) == 2:
        primary, backup = windows
        # Backup must not overlap primary
        assert backup[1] <= primary[0] or backup[0] >= primary[1]


def test_find_windows_empty_when_no_valid_start():
    df = _make_slots(48, start="2024-06-10 06:00")
    df = add_global_scores(df)
    fit = task_fit_scores(df, weather_profile=None, mode="balanced")
    # Window so narrow a 4h task can never fit
    windows = find_windows(fit, 240, "23:30", "23:59", tz=LONDON)
    assert windows == []


def test_find_windows_scores_descending():
    df = _make_slots(96, start="2024-06-10 06:00")
    df = add_global_scores(df)
    fit = task_fit_scores(df, weather_profile=None, mode="green")
    windows = find_windows(fit, 120, "06:00", "22:00", tz=LONDON)
    if len(windows) == 2:
        assert windows[0][2] >= windows[1][2]


def test_find_windows_overnight_ev():
    df = _make_slots(48, start="2024-06-10 22:00")
    df = add_global_scores(df)
    fit = task_fit_scores(df, weather_profile=None, mode="green")
    dl = datetime(2024, 6, 11, 7, 0, tzinfo=UTC)
    windows = find_windows(
        fit, 240, "22:00", "23:59",
        abs_deadline=dl, tz=LONDON,
    )
    assert len(windows) >= 1
    start, end, _ = windows[0]
    assert end.astimezone(UTC) <= dl


# ── savings.compute_savings ──────────────────────────────────────────────────


def test_compute_savings_ev_charge_nonneg():
    df = _make_slots(96, start="2024-06-10 06:00")
    task = TEMPLATES["ev_charge"]
    chosen_start = df.index[4]
    co2, cost = compute_savings(task, chosen_start, 240, df, tz=LONDON)
    assert co2 >= 0.0
    assert cost >= 0.0


def test_compute_savings_airdry_includes_dryer_avoidance():
    df = _make_slots(96, start="2024-06-10 06:00")
    df["ci_gco2"] = 100.0  # constant CI → shift saving = 0
    df["price_p"] = 15.0
    task = TEMPLATES["laundry_airdry"]
    chosen_start = df.index[20]
    co2, _ = compute_savings(task, chosen_start, 120, df, tz=LONDON)
    # avoided dryer: 3.5 kWh × 100 gCO2/kWh / 1000 = 0.35 kg
    assert co2 == pytest.approx(0.35, abs=0.01)


def test_compute_savings_no_price_column():
    df = _make_slots(96).drop(columns=["price_p"])
    df["ci_gco2"] = 200.0
    task = TEMPLATES["dishwasher"]
    chosen_start = df.index[0]
    co2, cost = compute_savings(task, chosen_start, 90, df, tz=LONDON)
    assert co2 >= 0.0
    assert cost == 0.0


# ── savings.build_reason ─────────────────────────────────────────────────────


def test_build_reason_includes_savings():
    reason = build_reason("dishwasher", "Dishwasher", 75.0, 70.0, None, 0.3, 0.15)
    assert "0.3" in reason or "0.15" in reason


def test_build_reason_airdry_mentions_dryer():
    reason = build_reason("laundry_airdry", "Laundry (air-dry)", 80.0, 75.0, 70.0, 0.5, 0.20)
    assert "dryer" in reason.lower()


def test_build_reason_fallback_when_no_savings():
    reason = build_reason("dishwasher", "Dishwasher", 30.0, 30.0, None, 0.0, 0.0)
    assert len(reason) > 0
