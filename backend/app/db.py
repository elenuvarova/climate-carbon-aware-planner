# Dialect is picked from DATABASE_URL so the same config works locally (SQLite) and on Render (Postgres).
from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

url = settings.database_url
_is_postgres = url.startswith("postgres://") or url.startswith("postgresql://")

if _is_postgres:
    db_kind = "postgres"
    # Render's Postgres connection strings sometimes use postgres:// — SQLAlchemy 2 needs postgresql://
    connect_url = url.replace("postgres://", "postgresql://", 1)
    engine = create_engine(
        connect_url,
        connect_args={"sslmode": "require"},
        pool_pre_ping=True,
    )
else:
    db_kind = "sqlite"
    engine = create_engine(
        f"sqlite:///{settings.sqlite_path}",
        connect_args={"check_same_thread": False},
    )

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_connection() -> None:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
