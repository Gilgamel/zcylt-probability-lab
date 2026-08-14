"""Persistence tests for the unified repository."""

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from config.domain import MATERIAL_PRODUCTION
from database.db import Base
from database.models import Category, Item, Observation, SimulationRun
from database.repository import ProbabilityRepository


def _repository_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'persistence.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory.begin() as session:
        category = Category(name="官匠营", category_type=MATERIAL_PRODUCTION)
        session.add(category)
        session.flush()
        session.add(Item(category_id=category.id, name="玉料"))
    return engine, factory


def test_observations_accumulate_across_database_sessions(tmp_path) -> None:
    """Committed unified observations survive closing and reopening sessions."""
    engine, factory = _repository_session(tmp_path)
    with factory.begin() as session:
        repository = ProbabilityRepository(session)
        repository.add_log("玉料", 9, 18, 1)
        repository.add_log("玉料", 9, 18, 2)
    engine.dispose()

    reopened = create_engine(f"sqlite:///{tmp_path / 'persistence.db'}")
    reopened_factory = sessionmaker(bind=reopened)
    with reopened_factory() as session:
        count = session.scalar(select(func.count()).select_from(Observation))
        totals = session.execute(select(
            func.sum(Observation.attempt_count), func.sum(Observation.orange_count)
        )).one()
    assert count == 2
    assert totals == (36, 3)


def test_simulation_metadata_is_persisted(tmp_path) -> None:
    """Model, seed, trials, and compact result remain reproducible."""
    _, factory = _repository_session(tmp_path)
    with factory.begin() as session:
        repository = ProbabilityRepository(session)
        repository.save_simulation_run(
            MATERIAL_PRODUCTION, "independent_bernoulli", 0.03,
            18, 100_000, 42, {"mean": 0.54}, "玉料",
        )
    with factory() as session:
        run = session.scalar(select(SimulationRun))
        assert run is not None
        assert (run.random_seed, run.simulation_runs, run.trial_count) == (42, 100_000, 18)


def test_observation_update_and_delete_work(tmp_path) -> None:
    """Unified CRUD retains edits and removes only the selected record."""
    _, factory = _repository_session(tmp_path)
    with factory.begin() as session:
        repository = ProbabilityRepository(session)
        observation = repository.add_log("玉料", 9, 18, 1, remark="before")
        observation_id = observation.id
    with factory.begin() as session:
        repository = ProbabilityRepository(session)
        repository.update_observation(
            observation_id, level=10, attempt_count=20, orange_count=2, remark="after"
        )
    with factory() as session:
        edited = session.get(Observation, observation_id)
        assert edited is not None
        assert (edited.level, edited.attempt_count, edited.orange_count, edited.remark) == (
            10, 20, 2, "after"
        )
    with factory.begin() as session:
        assert ProbabilityRepository(session).delete_observation(observation_id)
    with factory() as session:
        assert session.get(Observation, observation_id) is None
