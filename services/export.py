"""Stable, Excel-compatible CSV exports for raw observations."""

from datetime import datetime

import pandas as pd


EXPORT_COLUMNS = (
    "id",
    "session_id",
    "observed_at",
    "category",
    "item",
    "level",
    "attempt_count",
    "green_count",
    "blue_count",
    "purple_count",
    "orange_count",
    "unaccounted_count",
    "remark",
    "created_at",
    "updated_at",
)


def observation_export_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Return the documented raw-data schema in a deterministic column order."""
    missing = [column for column in EXPORT_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"导出数据缺少列：{', '.join(missing)}")
    exported = frame.loc[:, EXPORT_COLUMNS].copy()
    exported["session_id"] = exported["session_id"].astype(str)
    if not exported.empty:
        exported["observed_at"] = pd.to_datetime(
            exported["observed_at"], errors="coerce"
        ).dt.strftime("%Y-%m-%d")
        for column in ("created_at", "updated_at"):
            values = pd.to_datetime(exported[column], errors="coerce", utc=True)
            exported[column] = values.map(
                lambda value: "" if pd.isna(value) else value.isoformat()
            )
    return exported


def observations_csv_bytes(frame: pd.DataFrame) -> bytes:
    """Encode observations as UTF-8 with BOM so Excel opens Chinese text cleanly."""
    return observation_export_frame(frame).to_csv(index=False).encode("utf-8-sig")


def observation_csv_name(scope: str) -> str:
    """Create a filesystem-safe download name."""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"probabilitylab_observations_{scope}_{stamp}.csv"
