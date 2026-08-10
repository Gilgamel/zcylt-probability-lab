"""Persistence regression tests for the repository layer."""

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from database.db import Base
from database.models import Material, ProductionLog
from database.repository import ProbabilityRepository


def test_added_logs_accumulate_across_database_sessions(tmp_path) -> None:
    """Committed production logs must survive closing and reopening a session."""
    database_path = tmp_path / "persistence.db"
    engine = create_engine(f"sqlite:///{database_path}")
    Base.metadata.create_all(engine)
    test_session = sessionmaker(bind=engine, expire_on_commit=False)

    with test_session.begin() as session:
        session.add(Material(name="玉料"))

    with test_session.begin() as session:
        repository = ProbabilityRepository(session)
        repository.add_log("玉料", 9, 18, 1)
        repository.add_log("玉料", 9, 18, 2)

    engine.dispose()
    reopened_engine = create_engine(f"sqlite:///{database_path}")
    reopened_session = sessionmaker(bind=reopened_engine)
    with reopened_session() as session:
        row_count = session.scalar(select(func.count()).select_from(ProductionLog))
        totals = session.execute(select(
            func.sum(ProductionLog.quantity),
            func.sum(ProductionLog.red_quantity),
        )).one()

    assert row_count == 2
    assert totals == (36, 3)
