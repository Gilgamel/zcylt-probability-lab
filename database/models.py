"""PostgreSQL SQLAlchemy models for ProbabilityLab's seven persisted entities."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.db import Base
from config.timezone import application_today


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    category_type: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    items: Mapped[list["Item"]] = relationship(back_populates="category")


class Item(Base):
    __tablename__ = "items"
    __table_args__ = (
        UniqueConstraint("category_id", "name", name="uq_item_category_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), index=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    category: Mapped[Category] = relationship(back_populates="items")


class Observation(Base):
    __tablename__ = "observations"
    __table_args__ = (
        CheckConstraint("attempt_count > 0", name="ck_observation_attempt_positive"),
        CheckConstraint("level > 0", name="ck_observation_level_positive"),
        CheckConstraint("green_count >= 0", name="ck_observation_green_nonnegative"),
        CheckConstraint("blue_count >= 0", name="ck_observation_blue_nonnegative"),
        CheckConstraint("purple_count >= 0", name="ck_observation_purple_nonnegative"),
        CheckConstraint("orange_count >= 0", name="ck_observation_orange_nonnegative"),
        CheckConstraint("unaccounted_count >= 0", name="ck_observation_other_nonnegative"),
        CheckConstraint(
            "green_count + blue_count + purple_count + orange_count + "
            "unaccounted_count <= attempt_count",
            name="ck_observation_quality_lte_attempts",
        ),
        Index("ix_observations_category_date", "category_id", "observed_at"),
        Index(
            "ix_observations_category_item_level",
            "category_id",
            "item_id",
            "level",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), default=uuid4, nullable=False, index=True
    )
    observed_at: Mapped[date] = mapped_column(Date, default=application_today, index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), index=True)
    level: Mapped[int] = mapped_column(Integer, index=True)
    attempt_count: Mapped[int] = mapped_column(Integer)
    green_count: Mapped[int] = mapped_column(Integer, default=0)
    blue_count: Mapped[int] = mapped_column(Integer, default=0)
    purple_count: Mapped[int] = mapped_column(Integer, default=0)
    orange_count: Mapped[int] = mapped_column(Integer, default=0)
    unaccounted_count: Mapped[int] = mapped_column(Integer, default=0)
    remark: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    category: Mapped[Category] = relationship()
    item: Mapped[Item] = relationship()


class ProbabilityTarget(Base):
    __tablename__ = "probability_targets"
    __table_args__ = (
        UniqueConstraint(
            "category_id", "item_id", "level", "quality", name="uq_probability_target"
        ),
        CheckConstraint(
            "displayed_probability >= 0 AND displayed_probability <= 1",
            name="ck_displayed_probability_range",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), index=True)
    item_id: Mapped[int | None] = mapped_column(ForeignKey("items.id"), nullable=True)
    level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quality: Mapped[str] = mapped_column(String(20), nullable=False)
    displayed_probability: Mapped[float] = mapped_column(Float, nullable=False)
    source_note: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


Index(
    "uq_probability_target_scope",
    ProbabilityTarget.category_id,
    func.coalesce(ProbabilityTarget.item_id, 0),
    func.coalesce(ProbabilityTarget.level, -1),
    ProbabilityTarget.quality,
    unique=True,
)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)


class SkillProgression(Base):
    """Reference proficiency required for one skill-level transition."""

    __tablename__ = "skill_progressions"
    __table_args__ = (
        UniqueConstraint("from_level", "to_level", name="uq_skill_progression"),
        CheckConstraint("from_level > 0", name="ck_skill_from_level_positive"),
        CheckConstraint("to_level > from_level", name="ck_skill_levels_increase"),
        CheckConstraint(
            "required_proficiency > 0", name="ck_skill_proficiency_positive"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    from_level: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    to_level: Mapped[int] = mapped_column(Integer, nullable=False)
    required_proficiency: Mapped[int] = mapped_column(Integer, nullable=False)


class SimulationRun(Base):
    __tablename__ = "simulation_runs"
    __table_args__ = (
        CheckConstraint("probability >= 0 AND probability <= 1", name="ck_sim_probability_range"),
        CheckConstraint("trial_count > 0", name="ck_sim_trial_positive"),
        CheckConstraint("simulation_runs > 0", name="ck_sim_runs_positive"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), index=True)
    item_id: Mapped[int | None] = mapped_column(ForeignKey("items.id"), nullable=True)
    level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    probability: Mapped[float] = mapped_column(Float, nullable=False)
    trial_count: Mapped[int] = mapped_column(Integer, nullable=False)
    simulation_runs: Mapped[int] = mapped_column(Integer, nullable=False)
    random_seed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
