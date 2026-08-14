"""Schema and reference-data acceptance tests."""

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from config.domain import BIRD_RANDOM, HORSE_SEARCH, MATERIAL_PRODUCTION
from database.db import Base, _seed_reference_data
from database.models import Category, Item, ProbabilityTarget, Setting


def test_v11_reference_data_and_raw_probabilities_are_seeded(tmp_path) -> None:
    """Seed all systems while retaining the horse table's intentional 99% sum."""
    engine = create_engine(f"sqlite:///{tmp_path / 'seed.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory.begin() as session:
        _seed_reference_data(session)
    with factory() as session:
        categories = {
            row.category_type: row.id for row in session.scalars(select(Category))
        }
        assert set(categories) == {MATERIAL_PRODUCTION, HORSE_SEARCH, BIRD_RANDOM}
        item_counts = {
            category_type: session.scalar(
                select(func.count()).select_from(Item).where(
                    Item.category_id == category_id
                )
            )
            for category_type, category_id in categories.items()
        }
        assert item_counts == {
            MATERIAL_PRODUCTION: 9,
            HORSE_SEARCH: 4,
            BIRD_RANDOM: 4,
        }
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
        assert horse_sum == 0.99
        assert bird_sum == 1.0
        assert session.get(Setting, "default_quantity").value == "18"
        assert session.get(Setting, "default_iterations").value == "100000"
