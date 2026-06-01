from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    location: Mapped[str] = mapped_column(String, default="London")
    region_id: Mapped[int] = mapped_column(Integer, default=13)  # 13 = London
    mode: Mapped[str] = mapped_column(String, default="balanced")  # green | money | balanced
    horizon_hours: Mapped[int] = mapped_column(Integer, default=48)

    tasks: Mapped[list["Task"]] = relationship("Task", back_populates="plan", cascade="all, delete-orphan")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id"))
    type: Mapped[str] = mapped_column(String)
    duration_mins: Mapped[int] = mapped_column(Integer)
    window_start: Mapped[str] = mapped_column(String)   # ISO time string, e.g. "08:00"
    window_end: Mapped[str] = mapped_column(String)     # ISO time string, e.g. "22:00"
    deadline: Mapped[str | None] = mapped_column(String, nullable=True)
    kwh: Mapped[float] = mapped_column(Float, default=1.0)

    plan: Mapped["Plan"] = relationship("Plan", back_populates="tasks")
    recommendation: Mapped["Recommendation | None"] = relationship(
        "Recommendation", back_populates="task", uselist=False, cascade="all, delete-orphan"
    )


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), unique=True)
    primary_start: Mapped[str] = mapped_column(String)
    primary_end: Mapped[str] = mapped_column(String)
    backup_start: Mapped[str | None] = mapped_column(String, nullable=True)
    backup_end: Mapped[str | None] = mapped_column(String, nullable=True)
    carbon_saved_kg: Mapped[float] = mapped_column(Float, default=0.0)
    cost_saved_gbp: Mapped[float] = mapped_column(Float, default=0.0)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    reason: Mapped[str] = mapped_column(String, default="")

    task: Mapped["Task"] = relationship("Task", back_populates="recommendation")
