"""Neon/PostgreSQL configuration, schema, and seed tests."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from config.domain import BIRD_RANDOM, BIRD_TARGETED, HORSE_SEARCH, MATERIAL_PRODUCTION
from database import db
from database.db import (
    Base,
    DatabaseConfigurationError,
    _seed_reference_data,
    test_connection as _test_connection,
)
from database.models import (
    Category,
    Item,
    ProbabilityTarget,
    Setting,
    SkillProgression,
)


def test_database_url_requires_postgresql_and_has_no_fallback(monkeypatch) -> None:
    monkeypatch.setattr(db, "_streamlit_secret", lambda: "")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(DatabaseConfigurationError, match="DATABASE_URL"):
        db.get_database_url()
    monkeypatch.setenv("DATABASE_URL", "mysql+pymysql://host/database")
    with pytest.raises(DatabaseConfigurationError, match="PostgreSQL"):
        db.get_database_url()


def test_streamlit_secret_has_priority_and_url_is_normalized(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://environment/db")
    monkeypatch.setattr(
        db, "_streamlit_secret", lambda: "postgresql://secret/db"
    )
    assert db.get_database_url() == "postgresql+psycopg://secret/db"


def test_health_check_fails_closed_without_exposing_url(monkeypatch) -> None:
    monkeypatch.setattr(
        db, "test_connection", lambda: (_ for _ in ()).throw(RuntimeError("password=hidden"))
    )
    health = db.check_database_health()
    assert not health.available
    assert health.message == "数据库暂时无法连接，请稍后重试。"
    assert "hidden" not in health.message


def test_schema_compiles_for_postgresql_with_required_tables_and_types() -> None:
    dialect = postgresql.dialect()
    ddl = "\n".join(
        str(CreateTable(table).compile(dialect=dialect))
        for table in Base.metadata.sorted_tables
    )
    indexes = "\n".join(
        str(CreateIndex(index).compile(dialect=dialect))
        for table in Base.metadata.sorted_tables
        for index in table.indexes
    )
    assert set(Base.metadata.tables) == {
        "categories", "items", "observations", "probability_targets",
        "skill_progressions", "settings", "simulation_runs",
    }
    assert "JSONB" in ddl
    assert "TIMESTAMP WITH TIME ZONE" in ddl
    assert "observed_at DATE" in ddl
    assert "session_id UUID" in ddl
    assert "ix_observations_category_id" in indexes
    assert "ix_observations_item_id" in indexes
    assert "ix_observations_level" in indexes
    assert "ix_observations_observed_at" in indexes
    assert "ix_observations_session_id" in indexes
    assert "ix_observations_category_item_level" in indexes


def test_select_one_health_check_against_development(postgres_factory) -> None:
    assert _test_connection(postgres_factory.kw["bind"])


def test_reference_seed_is_idempotent_and_exact(postgres_factory) -> None:
    with postgres_factory.begin() as session:
        _seed_reference_data(session)
        _seed_reference_data(session)
    with postgres_factory() as session:
        categories = {
            row.category_type: row.id for row in session.scalars(select(Category))
        }
        assert {MATERIAL_PRODUCTION, HORSE_SEARCH, BIRD_RANDOM}.issubset(categories)
        counts = {
            category_type: session.scalar(
                select(func.count()).select_from(Item).where(Item.category_id == category_id)
            )
            for category_type, category_id in categories.items()
        }
        assert counts[MATERIAL_PRODUCTION] == 9
        assert counts[HORSE_SEARCH] == 4
        assert counts[BIRD_RANDOM] == 4
        if BIRD_TARGETED in counts:
            assert counts[BIRD_TARGETED] == 4
        horse_sum = session.scalar(
            select(func.sum(ProbabilityTarget.displayed_probability)).where(
                ProbabilityTarget.category_id == categories[HORSE_SEARCH]
            )
        )
        bird_sum = session.scalar(
            select(func.sum(ProbabilityTarget.displayed_probability)).where(
                ProbabilityTarget.category_id == categories[BIRD_RANDOM]
            )
        )
        assert horse_sum == pytest.approx(0.99)
        assert bird_sum == pytest.approx(1.0)
        expected = {
            "default_material_quantity": "18",
            "default_material_level": "12",
            "default_horse_level": "10",
            "default_bird_level": "10",
            "default_monte_carlo_iterations": "100000",
            "confidence_level": "0.95",
        }
        assert {key: session.get(Setting, key).value for key in expected} == expected
        progressions = [
            (row.from_level, row.to_level, row.required_proficiency)
            for row in session.scalars(
                select(SkillProgression).order_by(SkillProgression.from_level)
            )
        ]
        assert progressions == [(9, 10, 200), (10, 11, 800), (11, 12, 1600)]
