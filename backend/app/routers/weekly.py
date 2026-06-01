"""POST /api/weekly — 7-day outlook: best slot per day per task + Groq brief.

Uses Groq (llama-3.1-8b-instant, free tier) instead of Claude API for
natural language generation. Falls back to a structured template when
GROQ_API_KEY is not set so the endpoint works without any AI key.
"""
from datetime import timezone

import pandas as pd
from fastapi import APIRouter, HTTPException

from app.core.scheduler import find_windows
from app.core.scoring import task_fit_scores
from app.core.tasks import TEMPLATES
from app.providers.brief_groq import generate_brief
from app.routers.forecast import build_grid_7d
from app.schemas import DayBrief, WeeklyRequest, WeeklyResponse, WeeklyTaskRec

router = APIRouter()


def _per_day_deadline(local_day_start: pd.Timestamp, deadline_hhmm: str):
    """Absolute UTC deadline for an overnight task on a given calendar day.

    e.g. Mon midnight + deadline '07:00' → Tue 07:00 UTC.
    """
    dh, dm = map(int, deadline_hhmm.split(":"))
    local_dl = (local_day_start + pd.Timedelta(days=1)).replace(
        hour=dh, minute=dm, second=0, microsecond=0
    )
    return local_dl.to_pydatetime().astimezone(timezone.utc)


@router.post("/api/weekly", response_model=WeeklyResponse)
async def weekly(req: WeeklyRequest):
    if not req.tasks:
        raise HTTPException(status_code=422, detail="Provide at least one task")

    df, city_cfg = await build_grid_7d(req.city)

    now_local = pd.Timestamp.now(tz=city_cfg.tz)
    today_local = now_local.normalize()

    days_out: list[DayBrief] = []

    for day_offset in range(7):
        local_day_start = today_local + pd.Timedelta(days=day_offset)
        # 28 h window covers overnight tasks (e.g. EV charging 22:00→07:00)
        local_day_end = local_day_start + pd.Timedelta(hours=28)

        day_df = df[(df.index >= local_day_start) & (df.index < local_day_end)]
        if day_df.empty:
            continue

        # Avg score reported for the natural 24-h period only
        day_24 = df[
            (df.index >= local_day_start)
            & (df.index < local_day_start + pd.Timedelta(days=1))
        ]
        avg_carbon_score = round(
            float((day_24 if not day_24.empty else day_df)["carbon_score"].mean()), 1
        )

        date_str = local_day_start.strftime("%Y-%m-%d")
        day_label = local_day_start.strftime(f"%A {local_day_start.day} %b")

        task_recs: list[WeeklyTaskRec] = []
        for task_in in req.tasks:
            tmpl = TEMPLATES.get(task_in.type)
            if tmpl is None:
                continue

            fit = task_fit_scores(day_df, tmpl.weather_profile, "balanced")

            # For overnight tasks, inject a per-day absolute deadline so find_windows
            # doesn't compute "next 07:00 from now" (correct only for today).
            abs_dl = (
                _per_day_deadline(local_day_start, task_in.deadline)
                if task_in.deadline
                else None
            )

            windows = find_windows(
                fit_scores=fit,
                duration_mins=task_in.duration_mins,
                window_start=task_in.window_start,
                window_end=task_in.window_end,
                deadline=task_in.deadline,
                weather_profile=tmpl.weather_profile,
                slot_grid=day_df,
                tz=city_cfg.tz,
                abs_deadline=abs_dl,
            )

            if windows:
                best = windows[0]
                task_recs.append(WeeklyTaskRec(
                    task_type=task_in.type,
                    task_label=tmpl.label,
                    best_start=best[0].isoformat(),
                    best_end=best[1].isoformat(),
                    score=round(best[2], 1),
                ))
            else:
                task_recs.append(WeeklyTaskRec(
                    task_type=task_in.type,
                    task_label=tmpl.label,
                    best_start=None,
                    best_end=None,
                    score=0.0,
                ))

        days_out.append(DayBrief(
            date=date_str,
            day_label=day_label,
            avg_carbon_score=avg_carbon_score,
            tasks=task_recs,
        ))

    days_for_brief = [
        {
            "day_label": d.day_label,
            "avg_carbon_score": d.avg_carbon_score,
            "tasks": [
                {"task_label": t.task_label, "best_start": t.best_start, "score": t.score}
                for t in d.tasks
            ],
        }
        for d in days_out
    ]
    brief = await generate_brief(city_cfg.name, days_for_brief, city_cfg.carbon_label)

    return WeeklyResponse(
        location=city_cfg.name,
        city=req.city,
        carbon_label=city_cfg.carbon_label,
        days=days_out,
        brief=brief,
    )
