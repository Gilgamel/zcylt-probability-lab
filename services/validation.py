"""Category-aware observation and atomic CSV validation."""

from datetime import datetime as DateTime
from typing import Iterable
from uuid import UUID, uuid4

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from config.domain import (
    BIRD_RANDOM,
    BIRD_SPECIES,
    BIRD_TARGETED,
    HORSE_BREEDS,
    HORSE_SEARCH,
    MATERIAL_PRODUCTION,
    MATERIALS,
    SKILL_LEVELS,
)


class ObservationInput(BaseModel):
    """Validated normalized input for all supported game categories."""

    model_config = ConfigDict(str_strip_whitespace=True)

    category_type: str
    item: str
    level: int = Field(gt=0)
    attempt_count: int = Field(gt=0)
    green_count: int = Field(default=0, ge=0)
    blue_count: int = Field(default=0, ge=0)
    purple_count: int = Field(default=0, ge=0)
    orange_count: int = Field(default=0, ge=0)
    unaccounted_count: int = Field(default=0, ge=0)
    session_id: UUID = Field(default_factory=uuid4)
    observed_at: DateTime = Field(default_factory=DateTime.now)
    remark: str = ""

    @field_validator("category_type")
    @classmethod
    def valid_category(cls, value: str) -> str:
        if value not in {MATERIAL_PRODUCTION, HORSE_SEARCH, BIRD_RANDOM, BIRD_TARGETED}:
            raise ValueError("未知分类")
        return value

    @model_validator(mode="after")
    def category_rules(self) -> "ObservationInput":
        valid_items = {
            MATERIAL_PRODUCTION: MATERIALS,
            HORSE_SEARCH: HORSE_BREEDS,
            BIRD_RANDOM: BIRD_SPECIES,
            BIRD_TARGETED: BIRD_SPECIES,
        }
        if self.item not in valid_items[self.category_type]:
            raise ValueError("项目不属于所选分类")
        if self.category_type == MATERIAL_PRODUCTION and self.level not in SKILL_LEVELS:
            raise ValueError("官匠营技能等级必须是 9、10、11 或 12")
        if self.category_type in {HORSE_SEARCH, BIRD_RANDOM, BIRD_TARGETED} and self.attempt_count > 8:
            raise ValueError("搜索会话最多包含 8 次")
        quality_total = (
            self.green_count + self.blue_count + self.purple_count
            + self.orange_count + self.unaccounted_count
        )
        if quality_total > self.attempt_count:
            raise ValueError("品质数量合计不能大于尝试次数")
        if self.category_type == HORSE_SEARCH and quality_total != self.attempt_count:
            raise ValueError("搜索品质数量与搜索次数必须相等；未知结果请计入其他/未说明")
        if self.category_type in {BIRD_RANDOM, BIRD_TARGETED}:
            if self.attempt_count != 1:
                raise ValueError("每条灵禽院原始观测必须且只能代表 1 次搜索")
            if self.green_count or self.unaccounted_count:
                raise ValueError("灵禽院结果只允许蓝、紫、橙三种品质")
            if self.blue_count + self.purple_count + self.orange_count != 1:
                raise ValueError("每条灵禽院原始观测必须包含且只包含 1 个品质结果")
        return self


BIRD_QUALITIES = ("BLUE", "PURPLE", "ORANGE")


def _optional_observed_at(observed_at: DateTime | None) -> dict[str, DateTime]:
    """Only override the model's automatic timestamp when a caller supplies one."""
    return {} if observed_at is None else {"observed_at": observed_at}


def validate_material_entry(
    *,
    material: str,
    skill_level: int,
    quantity: int,
    orange_count: int,
    remark: str = "",
    session_id: UUID | None = None,
    observed_at: DateTime | None = None,
) -> ObservationInput:
    """Validate and normalize one 官匠营 production batch."""
    return ObservationInput(
        category_type=MATERIAL_PRODUCTION,
        item=material,
        level=skill_level,
        attempt_count=quantity,
        orange_count=orange_count,
        remark=remark,
        session_id=session_id or uuid4(),
        **_optional_observed_at(observed_at),
    )


def validate_horse_session(
    *,
    horse: str,
    level: int,
    search_count: int,
    green_count: int,
    blue_count: int,
    purple_count: int,
    orange_count: int,
    unaccounted_count: int = 0,
    remark: str = "",
    session_id: UUID | None = None,
    observed_at: DateTime | None = None,
) -> ObservationInput:
    """Validate and normalize an aggregate 马厩 search session."""
    return ObservationInput(
        category_type=HORSE_SEARCH,
        item=horse,
        level=level,
        attempt_count=search_count,
        green_count=green_count,
        blue_count=blue_count,
        purple_count=purple_count,
        orange_count=orange_count,
        unaccounted_count=unaccounted_count,
        remark=remark,
        session_id=session_id or uuid4(),
        **_optional_observed_at(observed_at),
    )


def validate_bird_session(
    *,
    level: int,
    results: Iterable[tuple[str, str]],
    remark: str = "",
    session_id: UUID | None = None,
    observed_at: DateTime | None = None,
    category_type: str = BIRD_RANDOM,
) -> list[ObservationInput]:
    """Validate 1–8 灵禽院 results and preserve each as one raw observation."""
    normalized_results = list(results)
    if not 1 <= len(normalized_results) <= 8:
        raise ValueError("灵禽院每个搜索会话必须包含 1 到 8 次结果")
    if category_type not in {BIRD_RANDOM, BIRD_TARGETED}:
        raise ValueError("未知的灵禽院培养方式")
    shared_session_id = session_id or uuid4()
    records: list[ObservationInput] = []
    for species, quality in normalized_results:
        if quality not in BIRD_QUALITIES:
            raise ValueError("灵禽院品质必须是蓝、紫或橙")
        records.append(ObservationInput(
            category_type=category_type,
            item=species,
            level=level,
            attempt_count=1,
            blue_count=int(quality == "BLUE"),
            purple_count=int(quality == "PURPLE"),
            orange_count=int(quality == "ORANGE"),
            remark=remark,
            session_id=shared_session_id,
            **_optional_observed_at(observed_at),
        ))
    return records


class ProductionInput(BaseModel):
    """Backward-compatible material input converted to ObservationInput."""

    model_config = ConfigDict(str_strip_whitespace=True)
    material: str
    skill_level: int
    quantity: int = Field(gt=0)
    red_quantity: int = Field(ge=0)
    datetime: DateTime = Field(default_factory=DateTime.now)
    remark: str = ""

    @model_validator(mode="after")
    def validate_production(self) -> "ProductionInput":
        ObservationInput(
            category_type=MATERIAL_PRODUCTION,
            item=self.material,
            level=self.skill_level,
            attempt_count=self.quantity,
            orange_count=self.red_quantity,
            observed_at=self.datetime,
            remark=self.remark,
        )
        return self


CSV_COLUMNS = (
    "observed_at", "category_type", "item", "level", "attempt_count",
    "green_count", "blue_count", "purple_count", "orange_count",
    "unaccounted_count", "remark",
    "session_id",
)


def validate_observation_csv(frame: pd.DataFrame) -> list[ObservationInput]:
    """Validate a unified CSV atomically and report source row numbers."""
    required = CSV_COLUMNS[:5]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"缺少列：{', '.join(missing)}")
    records: list[ObservationInput] = []
    errors: list[str] = []
    for position, row in frame.iterrows():
        try:
            payload = {column: row.get(column, 0) for column in CSV_COLUMNS}
            for column in ("green_count", "blue_count", "purple_count", "orange_count", "unaccounted_count"):
                payload[column] = 0 if pd.isna(payload[column]) else payload[column]
            raw_remark = row.get("remark", "")
            payload["remark"] = "" if pd.isna(raw_remark) else raw_remark
            raw_session_id = row.get("session_id", None)
            payload["session_id"] = (
                uuid4() if raw_session_id is None or pd.isna(raw_session_id)
                else str(raw_session_id)
            )
            records.append(ObservationInput.model_validate(payload))
        except Exception as exc:
            errors.append(f"第 {position + 2} 行：{exc}")
    if errors:
        raise ValueError("\n".join(errors))
    return records


def validate_csv(frame: pd.DataFrame) -> list[ProductionInput]:
    """Validate the legacy material CSV format atomically."""
    columns = ("datetime", "material", "skill_level", "quantity", "red_quantity")
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"缺少列：{', '.join(missing)}")
    records: list[ProductionInput] = []
    errors: list[str] = []
    for position, row in frame.iterrows():
        try:
            records.append(ProductionInput.model_validate({
                "datetime": row["datetime"],
                "material": row["material"],
                "skill_level": row["skill_level"],
                "quantity": row["quantity"],
                "red_quantity": row["red_quantity"],
                "remark": "" if pd.isna(row.get("remark", "")) else row.get("remark", ""),
            }))
        except Exception as exc:
            errors.append(f"第 {position + 2} 行：{exc}")
    if errors:
        raise ValueError("\n".join(errors))
    return records
