"""Slide-window scheduler: finds primary + backup windows for a task."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd

LONDON = ZoneInfo("Europe/London")


def _valid_starts(
    slots: pd.DatetimeIndex,
    window_start: str,   # "HH:MM" local city time
    window_end: str,     # "HH:MM" local city time
    duration_mins: int,
    deadline: str | None,  # "HH:MM" — must finish by next occurrence
    tz: ZoneInfo = LONDON,
    abs_deadline: datetime | None = None,  # pre-computed deadline (overrides deadline str)
) -> pd.DatetimeIndex:
    """Return slot starts where the task can begin and fits entirely within the window."""
    ws_h, ws_m = map(int, window_start.split(":"))
    we_h, we_m = map(int, window_end.split(":"))
    ws_tod = ws_h * 60 + ws_m
    we_tod = we_h * 60 + we_m
    duration = timedelta(minutes=duration_mins)

    # Build absolute deadline in UTC — use pre-computed if provided
    if abs_deadline is None and deadline:
        dl_h, dl_m = map(int, deadline.split(":"))
        now_utc = datetime.now(timezone.utc)
        now_local = now_utc.astimezone(tz)
        dl_local = now_local.replace(hour=dl_h, minute=dl_m, second=0, microsecond=0)
        if dl_local <= now_local:
            dl_local = dl_local + timedelta(days=1)
        abs_deadline = dl_local.astimezone(timezone.utc)

    # When a deadline applies the window may span midnight, so the lower bound is
    # an absolute instant (window_start on the eve of the deadline), NOT a daily
    # time-of-day. Gating on time-of-day would wrongly drop every post-midnight
    # start — exactly the cleanest small-hours slots an overnight task wants.
    abs_window_start: datetime | None = None
    if abs_deadline is not None:
        dl_local = abs_deadline.astimezone(tz)
        ws_local = dl_local.replace(hour=ws_h, minute=ws_m, second=0, microsecond=0)
        if ws_local >= dl_local:
            ws_local -= timedelta(days=1)
        abs_window_start = ws_local.astimezone(timezone.utc)

    valid = []
    for slot_utc in slots:
        slot_local = slot_utc.astimezone(tz)
        end_local = (slot_utc + duration).astimezone(tz)

        slot_tod = slot_local.hour * 60 + slot_local.minute
        end_tod = end_local.hour * 60 + end_local.minute

        if abs_deadline:
            if (slot_utc + duration) > abs_deadline:
                continue
            # Task may legally span midnight: only reject starts before the window opens.
            if abs_window_start is not None and slot_utc < abs_window_start:
                continue
        else:
            # No deadline: task must fit entirely within the daily window, same calendar day
            if slot_local.date() != end_local.date():
                continue
            if slot_tod < ws_tod or end_tod > we_tod:
                continue

        valid.append(slot_utc)

    return pd.DatetimeIndex(valid)


def find_windows(
    fit_scores: pd.Series,
    duration_mins: int,
    window_start: str,
    window_end: str,
    deadline: str | None = None,
    weather_profile: str | None = None,
    slot_grid: pd.DataFrame | None = None,
    tz: ZoneInfo = LONDON,
    abs_deadline: datetime | None = None,  # pre-computed deadline for weekly view
) -> list[tuple[datetime, datetime, float]]:
    """
    Returns up to 2 non-overlapping (start, end, mean_score) tuples, best first.
    An empty list means no valid window found.
    """
    duration = timedelta(minutes=duration_mins)
    n_slots = max(1, duration_mins // 30)
    valid = _valid_starts(
        fit_scores.index, window_start, window_end, duration_mins, deadline, tz,
        abs_deadline=abs_deadline,
    )

    # Hard gate for weather tasks: drying slots where it's raining (score==0) are invalid
    invalid_slots: set = set()
    if weather_profile == "drying" and slot_grid is not None and "weather_score_drying" in slot_grid.columns:
        rain_mask = slot_grid["weather_score_drying"] == 0.0
        invalid_slots = set(slot_grid.index[rain_mask])

    candidates: list[tuple[datetime, datetime, float]] = []
    for start in valid:
        end = start + duration
        if start not in fit_scores.index:
            continue
        start_pos = fit_scores.index.get_loc(start)
        window_vals = fit_scores.iloc[start_pos: start_pos + n_slots]
        if len(window_vals) < n_slots:
            continue
        if window_vals.isna().any():
            continue
        # Exclude windows that contain any rained-out slot
        if invalid_slots and any(s in invalid_slots for s in window_vals.index):
            continue
        candidates.append((start.to_pydatetime(), end.to_pydatetime(), float(window_vals.mean())))

    candidates.sort(key=lambda t: -t[2])

    if not candidates:
        return []

    primary = candidates[0]
    result = [primary]

    for cand in candidates[1:]:
        # Backup must not overlap with primary
        no_overlap = cand[1] <= primary[0] or cand[0] >= primary[1]
        if no_overlap:
            result.append(cand)
            break

    return result
