"""POST /api/compare — run all three optimisation modes in one call.

Returns the same slot grid plus three sets of recommendations (green, money,
balanced) so the frontend can show a side-by-side comparison without making
three separate plan requests.
"""
from fastapi import APIRouter, HTTPException

from app.routers.forecast import build_grid_with_scores, row_to_slot
from app.routers.plan import _build_recommendations
from app.schemas import CompareRequest, CompareResponse

router = APIRouter()

MODES = ["balanced", "green", "money"]


@router.post("/api/compare", response_model=CompareResponse)
async def compare(req: CompareRequest):
    if not req.tasks:
        raise HTTPException(status_code=422, detail="Provide at least one task")

    df, city_cfg = await build_grid_with_scores(req.city)
    slots = [row_to_slot(ts, row) for ts, row in df.iterrows()]

    modes: dict = {}
    for mode in MODES:
        modes[mode] = _build_recommendations(df, city_cfg, req.tasks, mode)

    return CompareResponse(
        location=city_cfg.name,
        city=req.city,
        carbon_label=city_cfg.carbon_label,
        slots=slots,
        modes=modes,
    )
