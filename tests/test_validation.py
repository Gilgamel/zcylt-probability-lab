"""Tests for entry and CSV validation."""

import pandas as pd
import pytest
from pydantic import ValidationError

from config.domain import (
    BIRD_RANDOM,
    BIRD_SPECIES,
    DEFAULTS,
    HORSE_SEARCH,
    MATERIAL_PRODUCTION,
)
from services.validation import (
    ObservationInput,
    ProductionInput,
    validate_bird_session,
    validate_bird_counts,
    validate_csv,
    validate_horse_session,
    validate_material_entry,
    validate_observation_csv,
)


def test_rejects_red_above_total() -> None:
    with pytest.raises(ValidationError):
        ProductionInput(material="玉料", skill_level=9, quantity=18, red_quantity=19)


def test_default_material_level_is_twelve() -> None:
    assert DEFAULTS["default_material_level"] == "12"


@pytest.mark.parametrize(
    "payload",
    [
        {"level": 8, "attempt_count": 18, "orange_count": 1},
        {"level": 9, "attempt_count": 0, "orange_count": 0},
        {"level": 9, "attempt_count": 18, "orange_count": 19},
    ],
)
def test_material_rejects_invalid_skill_quantity_or_orange(payload) -> None:
    with pytest.raises(ValidationError):
        ObservationInput(
            category_type=MATERIAL_PRODUCTION, item="玉料", **payload
        )


def test_csv_is_validated_atomically_with_row_number() -> None:
    frame = pd.DataFrame([
        {"datetime": "2026-08-01", "material": "玉料", "skill_level": 9, "quantity": 18, "red_quantity": 1},
        {"datetime": "2026-08-02", "material": "不存在", "skill_level": 9, "quantity": 18, "red_quantity": 1},
    ])
    with pytest.raises(ValueError, match="第 3 行"):
        validate_csv(frame)


def test_horse_session_is_limited_and_must_be_fully_accounted() -> None:
    with pytest.raises(ValidationError):
        ObservationInput(
            category_type=HORSE_SEARCH, item="浴火烈马", level=10,
            attempt_count=9, green_count=9,
        )
    with pytest.raises(ValidationError):
        ObservationInput(
            category_type=HORSE_SEARCH, item="浴火烈马", level=10,
            attempt_count=8, green_count=7,
        )


def test_bird_records_result_species_and_quality() -> None:
    record = ObservationInput(
        category_type=BIRD_RANDOM, item="铁羽雁", level=10,
        attempt_count=1, orange_count=1,
    )
    assert record.item == "铁羽雁"
    assert record.orange_count == 1

    with pytest.raises(ValidationError):
        ObservationInput(
            category_type=BIRD_RANDOM, item="不存在的灵禽", level=10,
            attempt_count=1, orange_count=1,
        )


def test_unified_csv_rejects_entire_file_with_source_row() -> None:
    frame = pd.DataFrame([
        {
            "observed_at": "2026-08-12", "category_type": HORSE_SEARCH,
            "item": "浴火烈马", "level": 10, "attempt_count": 1,
            "green_count": 1, "blue_count": 0, "purple_count": 0,
            "orange_count": 0, "unaccounted_count": 0,
        },
        {
            "observed_at": "2026-08-12", "category_type": HORSE_SEARCH,
            "item": "浴火烈马", "level": 10, "attempt_count": 8,
            "green_count": 2, "blue_count": 2, "purple_count": 0,
            "orange_count": 0, "unaccounted_count": 0,
        },
    ])
    with pytest.raises(ValueError, match="第 3 行"):
        validate_observation_csv(frame)


@pytest.mark.parametrize("orange", [0, 18])
def test_material_entry_accepts_boundary_orange_counts(orange: int) -> None:
    record = validate_material_entry(
        material="丝线", skill_level=9, quantity=18, orange_count=orange
    )
    assert (record.attempt_count, record.orange_count) == (18, orange)


def test_material_entry_rejects_orange_above_quantity() -> None:
    with pytest.raises(ValidationError):
        validate_material_entry(
            material="丝线", skill_level=9, quantity=18, orange_count=19
        )


@pytest.mark.parametrize("search_count", [1, 8])
def test_horse_session_accepts_one_to_eight_results(search_count: int) -> None:
    record = validate_horse_session(
        horse="浴火烈马", level=10, search_count=search_count,
        green_count=search_count, blue_count=0, purple_count=0, orange_count=0,
    )
    assert record.attempt_count == search_count


def test_horse_session_rejects_nine_results() -> None:
    with pytest.raises(ValidationError):
        validate_horse_session(
            horse="浴火烈马", level=10, search_count=9,
            green_count=9, blue_count=0, purple_count=0, orange_count=0,
        )


def test_bird_session_aggregates_eight_results_by_species() -> None:
    results = [
        ("铁羽雁", "BLUE"), ("九炎鹊", "PURPLE"),
        ("出云鹤", "ORANGE"), ("暗铁鸦", "BLUE"),
        ("铁羽雁", "BLUE"), ("九炎鹊", "PURPLE"),
        ("出云鹤", "BLUE"), ("暗铁鸦", "ORANGE"),
    ]
    records = validate_bird_session(level=10, results=results)
    assert len(records) == 4
    assert len({record.session_id for record in records}) == 1
    assert all(record.attempt_count == 2 for record in records)
    assert [record.item for record in records] == list(BIRD_SPECIES)
    assert all(
        record.blue_count + record.purple_count + record.orange_count
        == record.attempt_count
        for record in records
    )
    by_species = {record.item: record for record in records}
    assert by_species["铁羽雁"].blue_count == 2
    assert by_species["九炎鹊"].purple_count == 2
    assert (by_species["出云鹤"].blue_count, by_species["出云鹤"].orange_count) == (1, 1)


def test_bird_count_matrix_omits_empty_species_and_limits_session_to_eight() -> None:
    records = validate_bird_counts(
        level=10,
        counts={
            "铁羽雁": {"BLUE": 3, "PURPLE": 1, "ORANGE": 0},
            "出云鹤": {"BLUE": 2, "PURPLE": 1, "ORANGE": 1},
        },
    )
    assert {record.category_type for record in records} == {BIRD_RANDOM}
    assert {record.item for record in records} == {"铁羽雁", "出云鹤"}
    assert sum(record.attempt_count for record in records) == 8
    assert len({record.session_id for record in records}) == 1


@pytest.mark.parametrize("total", [0, 9])
def test_bird_count_matrix_rejects_total_outside_one_to_eight(total: int) -> None:
    with pytest.raises(ValueError, match="1 到 8"):
        validate_bird_counts(
            level=10,
            counts={"铁羽雁": {"BLUE": total}},
        )


@pytest.mark.parametrize(
    "results",
    [[("不存在的灵禽", "BLUE")], [("铁羽雁", "GREEN")]],
)
def test_bird_session_rejects_invalid_species_or_quality(results) -> None:
    with pytest.raises((ValidationError, ValueError)):
        validate_bird_session(level=10, results=results)
