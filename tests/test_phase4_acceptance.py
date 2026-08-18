"""Connected Neon Development acceptance test for Phase 4."""

from datetime import date, timedelta
from uuid import uuid4

from sqlalchemy import delete, func, select

from config.domain import BIRD_RANDOM, HORSE_SEARCH, MATERIAL_PRODUCTION
from database.models import Observation, SimulationRun
from database.repository import (
    AnalysisRepository,
    CategoryRepository,
    ItemRepository,
    SimulationRepository,
)
from services.monte_carlo import (
    BIRD_EQUAL_SPECIES_MODEL,
    BIRD_QUALITY_MODEL,
    HORSE_LITERAL_MODEL,
    MATERIAL_USER_MODEL,
    simulate_binary,
    simulate_multinomial,
)
from services.simulator import literal_horse_probabilities


def test_phase4_development_end_to_end_and_cleanup(postgres_factory) -> None:
    marker = f"phase4-acceptance-{uuid4()}"
    run_ids: list[int] = []
    observation_ids: list[int] = []
    today = date.today()
    with postgres_factory() as session:
        baseline_observations = session.scalar(select(func.count(Observation.id)))
        baseline_runs = session.scalar(select(func.count(SimulationRun.id)))
        assert baseline_observations == 0
    try:
        with postgres_factory.begin() as session:
            categories = CategoryRepository(session)
            items = ItemRepository(session)
            material_category = categories.by_type(MATERIAL_PRODUCTION)
            horse_category = categories.by_type(HORSE_SEARCH)
            bird_category = categories.by_type(BIRD_RANDOM)
            rows = [
                Observation(
                    session_id=uuid4(), observed_at=today, category_id=material_category.id,
                    item_id=items.by_name(MATERIAL_PRODUCTION, "玉料").id, level=9,
                    attempt_count=100, orange_count=4, remark=marker,
                ),
                Observation(
                    session_id=uuid4(), observed_at=today - timedelta(days=1),
                    category_id=material_category.id,
                    item_id=items.by_name(MATERIAL_PRODUCTION, "玉料").id, level=9,
                    attempt_count=50, orange_count=0, remark=marker,
                ),
                Observation(
                    session_id=uuid4(), observed_at=today, category_id=horse_category.id,
                    item_id=items.by_name(HORSE_SEARCH, "浴火烈马").id, level=10,
                    attempt_count=8, green_count=3, blue_count=4, orange_count=1, remark=marker,
                ),
                Observation(
                    session_id=uuid4(), observed_at=today, category_id=bird_category.id,
                    item_id=items.by_name(BIRD_RANDOM, "铁羽雁").id, level=10,
                    attempt_count=1, blue_count=1, remark=marker,
                ),
                Observation(
                    session_id=uuid4(), observed_at=today, category_id=bird_category.id,
                    item_id=items.by_name(BIRD_RANDOM, "九炎鹊").id, level=10,
                    attempt_count=1, purple_count=1, remark=marker,
                ),
            ]
            session.add_all(rows)
            session.flush()
            observation_ids.extend(row.id for row in rows)

        with postgres_factory.begin() as session:
            analysis = AnalysisRepository(session)
            material = analysis.material_summary("玉料", 9, today, today).iloc[0]
            horse = analysis.quality_summary(HORSE_SEARCH, "浴火烈马", 10, today, today).iloc[0]
            birds = analysis.quality_summary(BIRD_RANDOM, None, 10, today, today).iloc[0]
            species = analysis.quality_by_item(BIRD_RANDOM, 10, today, today)
            sessions = analysis.session_summary(HORSE_SEARCH, "浴火烈马", 10, today, today)
            assert (int(material.attempts), int(material.orange)) == (100, 4)
            assert (int(horse.attempts), int(horse.orange)) == (8, 1)
            assert (int(birds.attempts), int(birds.orange)) == (2, 0)
            assert int(species["attempts"].sum()) == 2
            assert (int(sessions.iloc[0].searches), int(sessions.iloc[0].orange)) == (8, 1)

            material_result = simulate_binary(0.03, 100, 10_000, 101, actual_successes=4, actual_trials=100)
            horse_model = literal_horse_probabilities(
                {"GREEN": 0.41, "BLUE": 0.50, "PURPLE": 0.07, "ORANGE": 0.01}
            )
            horse_result = simulate_multinomial(
                horse_model, 8, 10_000, 102,
                actual_counts={"GREEN": 3, "BLUE": 4, "PURPLE": 0, "ORANGE": 1, "OTHER": 0},
                actual_trials=8,
            )
            bird_quality = simulate_multinomial(
                {"BLUE": 0.79, "PURPLE": 0.20, "ORANGE": 0.01}, 2, 10_000, 103,
                actual_counts={"BLUE": 1, "PURPLE": 1, "ORANGE": 0}, actual_trials=2,
            )
            bird_species = simulate_multinomial(
                {"铁羽雁": 0.25, "九炎鹊": 0.25, "出云鹤": 0.25, "暗铁鸦": 0.25},
                2, 10_000, 104,
                actual_counts={"铁羽雁": 1, "九炎鹊": 1, "出云鹤": 0, "暗铁鸦": 0}, actual_trials=2,
            )
            assert material_result.actual_comparable
            assert horse_result.actual_comparable
            assert bird_quality.actual_comparable
            assert bird_species.actual_comparable
            assert material_result.outcome.actual_percentile is not None
            assert all(
                value.actual_percentile is not None
                for value in horse_result.per_category.values()
            )
            repository = SimulationRepository(session)
            cases = [
                (MATERIAL_PRODUCTION, MATERIAL_USER_MODEL, 0.03, material_result, "玉料", 9),
                (HORSE_SEARCH, HORSE_LITERAL_MODEL, 0.01, horse_result, "浴火烈马", 10),
                (BIRD_RANDOM, BIRD_QUALITY_MODEL, 0.01, bird_quality, None, 10),
                (BIRD_RANDOM, BIRD_EQUAL_SPECIES_MODEL, 0.25, bird_species, None, 10),
            ]
            for category, name, probability, result, item, level in cases:
                payload = result.storage_dict()
                run = repository.add(
                    category, name, probability, result.trial_count,
                    result.simulation_count, result.random_seed, payload, item, level,
                )
                run_ids.append(run.id)
                assert "samples" not in payload
            history = repository.recent_dataframe(20)
            stored = history[history["id"].isin(run_ids)]
            assert len(stored) == 4
            assert all(payload["result_version"] == 1 for payload in stored["result_json"])
            stored_by_model = stored.set_index("model_name")
            assert stored_by_model.loc[MATERIAL_USER_MODEL, "actual_result"] == 4
            assert stored_by_model.loc[HORSE_LITERAL_MODEL, "actual_result"] == {
                "GREEN": 3, "BLUE": 4, "PURPLE": 0, "ORANGE": 1, "OTHER": 0,
            }
    finally:
        with postgres_factory.begin() as session:
            if run_ids:
                session.execute(delete(SimulationRun).where(SimulationRun.id.in_(run_ids)))
            if observation_ids:
                session.execute(delete(Observation).where(Observation.id.in_(observation_ids)))
        with postgres_factory() as session:
            assert session.scalar(select(func.count(Observation.id))) == baseline_observations
            assert session.scalar(select(func.count(SimulationRun.id))) == baseline_runs
            assert session.scalar(
                select(func.count(Observation.id)).where(Observation.remark == marker)
            ) == 0
