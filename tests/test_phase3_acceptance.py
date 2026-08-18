"""Phase 3 aggregate-analysis acceptance against Neon Development only."""

from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import plotly.graph_objects as go
from sqlalchemy import func, select

from charts.statistical_charts import cumulative_rate_chart, rate_with_ci_chart
from config.domain import BIRD_RANDOM, HORSE_SEARCH
from database.models import Observation
from database.repository import AnalysisRepository, ObservationRepository
from services.analysis import complete_level_table, cumulative_daily, proportion_table
from services.statistics import calculate_binomial_test, calculate_proportion
from services.validation import validate_bird_session, validate_horse_session


def _add(repository: ObservationRepository, record, marker: str) -> int:
    return repository.add(
        category_type=record.category_type, item_name=record.item, level=record.level,
        attempt_count=record.attempt_count, observed_at=record.observed_at,
        green_count=record.green_count, blue_count=record.blue_count,
        purple_count=record.purple_count, orange_count=record.orange_count,
        unaccounted_count=record.unaccounted_count, session_id=record.session_id,
        remark=marker,
    ).id


def test_phase3_neon_development_aggregates_and_cleanup(postgres_factory) -> None:
    marker = f"phase3-acceptance-{uuid4().hex}"
    ids: list[int] = []
    with postgres_factory() as session:
        baseline = int(session.scalar(select(func.count()).select_from(Observation)) or 0)
        baseline_analysis = AnalysisRepository(session)
        baseline_dashboard = baseline_analysis.dashboard_totals().set_index("category_type")
        baseline_material = int(baseline_analysis.material_summary("玉料")["attempts"].sum())
        baseline_horse = int(baseline_analysis.quality_summary(HORSE_SEARCH, level=10).iloc[0]["attempts"])
        baseline_bird = int(baseline_analysis.quality_summary(BIRD_RANDOM, level=10).iloc[0]["attempts"])
    try:
        with postgres_factory.begin() as session:
            repository = ObservationRepository(session)
            for offset, (level, orange) in enumerate(((9, 1), (10, 3), (11, 5), (12, 8))):
                ids.append(repository.add_material(
                    "玉料", level, 100, orange,
                    observed_at=date.today() - timedelta(days=3 - offset), remark=marker,
                ).id)
            horse_records = [
                validate_horse_session(horse="浴火烈马", level=10, search_count=8, green_count=3, blue_count=4, purple_count=0, orange_count=1),
                validate_horse_session(horse="踏水飞马", level=10, search_count=8, green_count=4, blue_count=3, purple_count=1, orange_count=0),
            ]
            for record in horse_records:
                ids.append(_add(repository, record, marker))
            for record in validate_bird_session(
                level=10,
                results=[("铁羽雁", "BLUE"), ("九炎鹊", "PURPLE"), ("出云鹤", "ORANGE"), ("暗铁鸦", "BLUE")],
            ):
                ids.append(_add(repository, record, marker))
            # Database constraints permit these legacy-shaped rows, but Phase 3
            # analysis must exclude them because they violate category semantics.
            ids.append(repository.add_material(
                "玉料", 8, 50, 5, remark=marker
            ).id)
            ids.append(repository.add(
                HORSE_SEARCH, "浴火烈马", 10, 8,
                green_count=3, blue_count=4, remark=marker,
            ).id)
            ids.append(repository.add(
                BIRD_RANDOM, "铁羽雁", 10, 2,
                blue_count=1, remark=marker,
            ).id)

        with postgres_factory() as session:
            analysis = AnalysisRepository(session)
            dashboard = analysis.dashboard_totals()
            dashboard_daily = analysis.daily_totals()
            assert {"MATERIAL_PRODUCTION", "HORSE_SEARCH", "BIRD_RANDOM"}.issubset(set(dashboard["category_type"]))
            assert not dashboard_daily.empty
            dashboard_indexed = dashboard.set_index("category_type")
            assert int(dashboard_indexed.loc["MATERIAL_PRODUCTION", "records"] - baseline_dashboard.loc["MATERIAL_PRODUCTION", "records"]) == 4
            assert int(dashboard_indexed.loc["MATERIAL_PRODUCTION", "attempts"] - baseline_dashboard.loc["MATERIAL_PRODUCTION", "attempts"]) == 400
            assert int(dashboard_indexed.loc[HORSE_SEARCH, "records"] - baseline_dashboard.loc[HORSE_SEARCH, "records"]) == 2
            assert int(dashboard_indexed.loc[HORSE_SEARCH, "attempts"] - baseline_dashboard.loc[HORSE_SEARCH, "attempts"]) == 16
            assert int(dashboard_indexed.loc[BIRD_RANDOM, "records"] - baseline_dashboard.loc[BIRD_RANDOM, "records"]) == 4
            assert int(dashboard_indexed.loc[BIRD_RANDOM, "attempts"] - baseline_dashboard.loc[BIRD_RANDOM, "attempts"]) == 4
            material = analysis.material_summary("玉料")
            assert int(material["attempts"].sum()) - baseline_material == 400
            marker_rows = session.scalars(select(Observation).where(Observation.id.in_(ids))).all()
            assert len(marker_rows) == 13
            material_result = calculate_proportion(17, 400)
            assert material_result.observed_rate == 17 / 400
            assert material_result.ci_low < material_result.observed_rate < material_result.ci_high

            levels = complete_level_table(material)
            assert set(levels["level"]) == {9, 10, 11, 12}
            daily = cumulative_daily(analysis.material_daily("玉料"))
            assert isinstance(cumulative_rate_chart(daily), go.Figure)
            assert isinstance(rate_with_ci_chart(levels, "level"), go.Figure)

            horse = analysis.quality_summary(HORSE_SEARCH, level=10)
            assert int(horse.iloc[0]["attempts"]) - baseline_horse == 16
            horse_by_breed = proportion_table(analysis.quality_by_item(HORSE_SEARCH, 10), "item")
            assert {"浴火烈马", "踏水飞马"}.issubset(set(horse_by_breed["item"]))
            assert 0 <= calculate_binomial_test(1, 16, 0.01).p_value <= 1

            bird = analysis.quality_summary(BIRD_RANDOM, level=10)
            assert int(bird.iloc[0]["attempts"]) - baseline_bird == 4
            bird_items = analysis.quality_by_item(BIRD_RANDOM, 10)
            assert set(("铁羽雁", "九炎鹊", "出云鹤", "暗铁鸦")).issubset(set(bird_items["item"]))
    finally:
        with postgres_factory.begin() as session:
            repository = ObservationRepository(session)
            for observation_id in ids:
                repository.delete(observation_id)
        with postgres_factory() as session:
            final_count = int(session.scalar(select(func.count()).select_from(Observation)) or 0)
            assert final_count == baseline
            assert session.scalar(select(func.count()).select_from(Observation).where(Observation.remark == marker)) == 0
