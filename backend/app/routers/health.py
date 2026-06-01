from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.db import check_connection, db_kind

router = APIRouter()


@router.get("/api/health")
def health():
    try:
        check_connection()
        return {"status": "ok", "db": db_kind}
    except Exception as exc:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(exc)})


@router.get("/api/hello")
def hello():
    return {"message": "Hello from the backend 👋"}
