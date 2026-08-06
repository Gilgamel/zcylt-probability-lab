"""Tests for entry and CSV validation."""

import pandas as pd
import pytest
from pydantic import ValidationError

from services.validation import ProductionInput, validate_csv


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
