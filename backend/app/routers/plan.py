import math
from datetime import timedelta

from fastapi import APIRouter, HTTPException

from app.core.savings import build_reason, compute_savings
from app.core.scheduler import find_windows
from app.core.scoring import task_fit_scores
from app.core.tasks import TEMPLATES
from app.routers.forecast import build_grid_with_scores, row_to_slot
from app.schemas import PlanRequest, PlanResponse, RecommendationOut


router = APIRouter()


def _build_recommendations(df, city_cfg, tasks_in, mode: str) -> list[RecommendationOut]:
    """Shared recommendation builder used by /plan and /compare."""
    recommendations = []

    for task_in in tasks_in:
        tmpl = TEMPLATES.get(task_in.type)
        if tmpl is None:
            raise HTTPException(status_code=422, detail=f"Unknown task type: {task_in.type!r}")

        fit = task_fit_scores(df, tmpl.weather_profile, mode)

        windows = find_windows(
            fit_scores=fit,
            duration_mins=task_in.duration_mins,
            window_start=task_in.window_start,
            window_end=task_in.window_end,
            deadline=task_in.deadline,
            weather_profile=tmpl.weather_profile,
            slot_grid=df,
            tz=city_cfg.tz,
        )

        if not windows:
            # Fallback: best contiguous window ignoring daily time constraints
            n = max(1, task_in.duration_mins // 30)
            best_score, best_pos = -1.0, 0
            for i in range(len(fit) - n + 1):
                w = fit.iloc[i: i + n]
                if not w.isna().any():
                    s = float(w.mean())
                    if s > best_score:
                        best_score, best_pos = s, i
            start = fit.index[best_pos].to_pydatetime()
            end = start + timedelta(minutes=task_in.duration_mins)
            windows = [(start, end, best_score)]

        primary = windows[0]
        backup = windows[1] if len(windows) > 1 else None

        p_start, p_end = primary[0], primary[1]
        mask = (df.index >= p_start) & (df.index < p_end)
        window_df = df[mask] if mask.any() else df.iloc[:1]

        def _w(col):
            s = window_df[col] if col in window_df.columns else None
            if s is None or s.empty or s.isna().all():
                return None
            v = float(s.mean())
            return None if math.isnan(v) else round(v, 1)

        carbon_s = _w("carbon_score") or 50.0
        price_s = _w("price_score")
        weather_col = f"weather_score_{tmpl.weather_profile}" if tmpl.weather_profile else None
        weather_s = _w(weather_col) if weather_col else None

        carbon_saved, cost_saved = compute_savings(
            tmpl, p_start, task_in.duration_mins, df, city_cfg.tz
        )
        reason = build_reason(task_in.type, tmpl.label, carbon_s, price_s, weather_s, carbon_saved, cost_saved)

        recommendations.append(RecommendationOut(
            task_type=task_in.type,
            task_label=tmpl.label,
            duration_mins=task_in.duration_mins,
            primary_start=p_start.isoformat(),
            primary_end=p_end.isoformat(),
            backup_start=backup[0].isoformat() if backup else None,
            backup_end=backup[1].isoformat() if backup else None,
            carbon_saved_kg=carbon_saved,
            cost_saved_gbp=cost_saved,
            score=round(float(primary[2]), 1),
            reason=reason,
        ))

    return recommendations


@router.post("/api/plan", response_model=PlanResponse)
async def plan(req: PlanRequest):
    if not req.tasks:
        raise HTTPException(status_code=422, detail="Provide at least one task")

    df, city_cfg = await build_grid_with_scores(req.city)
    slots = [row_to_slot(ts, row) for ts, row in df.iterrows()]
    recommendations = _build_recommendations(df, city_cfg, req.tasks, req.mode)

    return PlanResponse(
        recommendations=recommendations,
        slots=slots,
        mode=req.mode,
        location=city_cfg.name,
        city=req.city,
        carbon_label=city_cfg.carbon_label,
    )
