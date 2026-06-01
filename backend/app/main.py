import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import http_client
from app.config import settings
from app.db import Base, db_kind, engine
from app.routers import compare, forecast, health, plan

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await http_client.init()
    Base.metadata.create_all(bind=engine)
    log.info("db: %s", db_kind)
    yield
    await http_client.close()


app = FastAPI(title="Climate & Carbon-Aware Planner", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(forecast.router)
app.include_router(plan.router)
app.include_router(compare.router)

# Serve built frontend in production
_public = Path(__file__).parent.parent / "public"
if settings.node_env == "production" and _public.exists():
    app.mount("/assets", StaticFiles(directory=str(_public / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str):
        return FileResponse(str(_public / "index.html"))
