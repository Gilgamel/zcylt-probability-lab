"""Tests for entry and CSV validation."""

import pandas as pd
import pytest
from pydantic import ValidationError

from config.settings import BIRD_RANDOM, HORSE_SEARCH
from services.validation import (
    ObservationInput,
    ProductionInput,
    validate_csv,
    validate_observation_csv,
)


def test_rejects_red_above_total() -> None:
    with pytest.raises(ValidationError):
        ProductionInput(material="玉料", skill_level=9, quantity=18, red_quantity=19)


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
