import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.db import check_connection, db_kind

log = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/health")
def health():
    try:
        check_connection()
        return {"status": "ok", "db": db_kind}
    except Exception:
        # Log the detail server-side; never leak DB host/driver to the client.
        log.exception("health check: database connection failed")
        return JSONResponse(status_code=500, content={"status": "error"})


@router.get("/api/hello")
def hello():
    return {"message": "Hello from the backend 👋"}
