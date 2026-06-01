"""GET /api/plans — recent plan history.
POST /api/feedback — record whether user followed a recommendation.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload

from app import models
from app.core.tasks import TEMPLATES
from app.db import get_db
from app.schemas import FeedbackIn, PlanHistoryItem, PlansResponse, RecommendationOut

log = logging.getLogger(__name__)
router = APIRouter()

CITY_SLUG = {
    "London": "london",
    "Paris": "paris",
    "Antwerp": "antwerp",
}


def _rec_out(task: "models.Task") -> RecommendationOut | None:
    rec = task.recommendation
    if rec is None:
        return None
    tmpl = TEMPLATES.get(task.type)
    return RecommendationOut(
        task_type=task.type,
        task_label=tmpl.label if tmpl else task.type,
        duration_mins=task.duration_mins,
        primary_start=rec.primary_start,
        primary_end=rec.primary_end,
        backup_start=rec.backup_start,
        backup_end=rec.backup_end,
        carbon_saved_kg=rec.carbon_saved_kg,
        cost_saved_gbp=rec.cost_saved_gbp,
        score=rec.score,
        reason=rec.reason,
    )


@router.get("/api/plans", response_model=PlansResponse)
def get_plans(limit: int = 20, db: Session = Depends(get_db)):
    plans = (
        db.query(models.Plan)
        .options(selectinload(models.Plan.tasks).selectinload(models.Task.recommendation))
        .order_by(models.Plan.created_at.desc())
        .limit(min(limit, 50))
        .all()
    )
    items = []
    for p in plans:
        recs = [r for t in p.tasks if (r := _rec_out(t)) is not None]
        items.append(PlanHistoryItem(
            id=p.id,
            created_at=p.created_at.isoformat(),
            location=p.location,
            mode=p.mode,
            city=CITY_SLUG.get(p.location, "london"),
            recommendations=recs,
        ))
    return PlansResponse(plans=items)


@router.post("/api/feedback", status_code=201)
def submit_feedback(req: FeedbackIn, db: Session = Depends(get_db)):
    plan = db.get(models.Plan, req.plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    if req.rating is not None and not (1 <= req.rating <= 5):
        raise HTTPException(status_code=422, detail="Rating must be 1–5")
    db.add(models.Feedback(
        plan_id=req.plan_id,
        task_type=req.task_type,
        followed=req.followed,
        rating=req.rating,
    ))
    db.commit()
    return {"ok": True}
