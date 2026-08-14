"""Unified SQLAlchemy ORM models for all tracked game systems."""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.db import Base


class Category(Base):
    """A top-level game system such as 官匠营, 马厩, or 灵禽院."""

    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    category_type: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    items: Mapped[list["Item"]] = relationship(back_populates="category")


class Item(Base):
    """A material, selected horse breed, or resulting bird species."""

    __tablename__ = "items"
    __table_args__ = (UniqueConstraint("category_id", "name", name="uq_item_category_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), index=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    category: Mapped[Category] = relationship(back_populates="items")


class Observation(Base):
    """One raw observation batch in any supported game system."""

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
            "green_count + blue_count + purple_count + orange_count + unaccounted_count <= attempt_count",
            name="ck_observation_quality_lte_attempts",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, index=True)
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
    session_key: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    category: Mapped[Category] = relationship()
    item: Mapped[Item] = relationship()


class ProbabilityTarget(Base):
    """An official displayed probability, kept separate from fitted values."""

    __tablename__ = "probability_targets"
    __table_args__ = (
        UniqueConstraint("category_id", "item_id", "level", "quality", name="uq_probability_target"),
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


class Setting(Base):
    """Persistent application setting stored as text."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)


class SimulationRun(Base):
    """Persisted simulation metadata and summarized results."""

    __tablename__ = "simulation_runs"
    __table_args__ = (
        CheckConstraint("probability >= 0 AND probability <= 1", name="ck_sim_probability_range"),
        CheckConstraint("trial_count > 0", name="ck_sim_trial_positive"),
        CheckConstraint("simulation_runs > 0", name="ck_sim_runs_positive"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), index=True)
    item_id: Mapped[int | None] = mapped_column(ForeignKey("items.id"), nullable=True)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    probability: Mapped[float] = mapped_column(Float, nullable=False)
    trial_count: Mapped[int] = mapped_column(Integer, nullable=False)
    simulation_runs: Mapped[int] = mapped_column(Integer, nullable=False)
    random_seed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result_json: Mapped[str] = mapped_column(Text, nullable=False)
