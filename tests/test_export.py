"""Tests for the stable raw-observation CSV contract."""

from io import BytesIO
from uuid import uuid4

import pandas as pd

from services.export import EXPORT_COLUMNS, observation_export_frame, observations_csv_bytes


def _source_frame() -> pd.DataFrame:
    now = pd.Timestamp("2026-08-14T12:34:56Z")
    return pd.DataFrame([{
        "id": 7, "session_id": uuid4(),
        "observed_at": pd.Timestamp("2026-08-14"),
        "category": "官匠营", "category_type": "MATERIAL_PRODUCTION",
        "item": "丝线", "level": 9, "attempt_count": 18,
        "green_count": 0, "blue_count": 0, "purple_count": 0,
        "orange_count": 1, "unaccounted_count": 0,
        "remark": "中文备注", "created_at": now, "updated_at": now,
    }])


def test_export_uses_exact_documented_column_order() -> None:
    exported = observation_export_frame(_source_frame())
    assert tuple(exported.columns) == EXPORT_COLUMNS
    assert exported.loc[0, "observed_at"] == "2026-08-14"


def test_csv_is_excel_compatible_utf8_and_preserves_chinese() -> None:
    payload = observations_csv_bytes(_source_frame())
    assert payload.startswith(b"\xef\xbb\xbf")
    loaded = pd.read_csv(BytesIO(payload), encoding="utf-8-sig")
    assert tuple(loaded.columns) == EXPORT_COLUMNS
    assert loaded.loc[0, "item"] == "丝线"
    assert loaded.loc[0, "remark"] == "中文备注"
