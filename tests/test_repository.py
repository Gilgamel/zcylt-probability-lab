"""PostgreSQL repository CRUD and transaction tests."""

from __future__ import annotations

from time import sleep
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from config.domain import MATERIAL_PRODUCTION
from database.models import Observation, SimulationRun
from database.repository import (
    CategoryRepository,
    ItemRepository,
    ObservationRepository,
    SimulationRepository,
    SkillProgressionRepository,
)


def test_category_and_item_crud(postgres_factory) -> None:
    marker = uuid4().hex
    with postgres_factory.begin() as session:
        categories = CategoryRepository(session)
        items = ItemRepository(session)
        category = categories.create(f"测试分类-{marker}", f"TEST_{marker}")
        category_id = category.id
        category = categories.update(category_id, name=f"已更新-{marker}")
        assert category.name == f"已更新-{marker}"
        item = items.create(category_id, f"测试项目-{marker}")
        item_id = item.id
        item = items.update(item_id, active=False)
        assert item.active is False
        assert items.delete(item_id)
        assert categories.delete(category_id)


def test_observation_crud_and_accumulation(postgres_factory) -> None:
    marker = uuid4().hex
    ids: list[int] = []
    try:
        with postgres_factory.begin() as session:
            repository = ObservationRepository(session)
            first = repository.add_material("玉料", 9, 18, 1, remark=marker)
            assert first.session_id is not None
            ids.append(first.id)
            ids.append(repository.add_material("玉料", 9, 18, 2, remark=marker).id)
        with postgres_factory() as session:
            count = session.scalar(
                select(func.count()).select_from(Observation).where(Observation.remark == marker)
            )
            totals = session.execute(
                select(func.sum(Observation.attempt_count), func.sum(Observation.orange_count))
                .where(Observation.remark == marker)
            ).one()
            assert count == 2
            assert totals == (36, 3)
            original_updated_at = session.get(Observation, ids[0]).updated_at
        sleep(0.02)
        with postgres_factory.begin() as session:
            ObservationRepository(session).update(
                ids[0], level=10, attempt_count=20, orange_count=2, remark=marker
            )
        with postgres_factory() as session:
            edited = session.get(Observation, ids[0])
            assert (edited.level, edited.attempt_count, edited.orange_count) == (10, 20, 2)
            assert edited.updated_at > original_updated_at
    finally:
        with postgres_factory.begin() as session:
            for observation_id in ids:
                ObservationRepository(session).delete(observation_id)


def test_transaction_rolls_back_all_rows(postgres_factory) -> None:
    marker = uuid4().hex
    with pytest.raises(RuntimeError):
        with postgres_factory.begin() as session:
            ObservationRepository(session).add_material("金精", 9, 18, 1, remark=marker)
            raise RuntimeError("force rollback")
    with postgres_factory() as session:
        assert session.scalar(
            select(func.count()).select_from(Observation).where(Observation.remark == marker)
        ) == 0


def test_simulation_jsonb_metadata(postgres_factory) -> None:
    with postgres_factory.begin() as session:
        run = SimulationRepository(session).add(
            MATERIAL_PRODUCTION, "independent_bernoulli", 0.03,
            18, 100_000, 42, {"mean": 0.54}, "玉料", level=9,
        )
        run_id = run.id
    try:
        with postgres_factory() as session:
            saved = session.get(SimulationRun, run_id)
            assert saved.result_json == {"mean": 0.54}
            assert saved.random_seed == 42
            assert saved.level == 9
    finally:
        with postgres_factory.begin() as session:
            saved = session.get(SimulationRun, run_id)
            if saved:
                session.delete(saved)


def test_skill_progression_repository_returns_reference_data(postgres_factory) -> None:
    with postgres_factory() as session:
        repository = SkillProgressionRepository(session)
        assert [
            (row.from_level, row.to_level, row.required_proficiency)
            for row in repository.all()
        ] == [(9, 10, 200), (10, 11, 800), (11, 12, 1600)]
