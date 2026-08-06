"""Input and CSV validation."""

from datetime import datetime as DateTime

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from config.settings import MATERIALS, SKILL_LEVELS


class ProductionInput(BaseModel):
    """Validated production observation."""

    model_config = ConfigDict(str_strip_whitespace=True)

    material: str
    skill_level: int
    quantity: int = Field(gt=0)
    red_quantity: int = Field(ge=0)
    datetime: DateTime = Field(default_factory=DateTime.now)
    remark: str = ""

    @field_validator("material")
    @classmethod
    def known_material(cls, value: str) -> str:
        if value not in MATERIALS:
            raise ValueError("材料不存在")
        return value

    @field_validator("skill_level")
    @classmethod
    def valid_skill(cls, value: int) -> int:
        if value not in SKILL_LEVELS:
            raise ValueError("技能等级必须是 9、10、11 或 12")
        return value

    @model_validator(mode="after")
    def red_not_greater_than_total(self) -> "ProductionInput":
        if self.red_quantity > self.quantity:
            raise ValueError("红色数量不能大于生产数量")
        return self


CSV_COLUMNS = ("datetime", "material", "skill_level", "quantity", "red_quantity", "remark")


def validate_csv(frame: pd.DataFrame) -> list[ProductionInput]:
    """Validate an entire import atomically, identifying bad row numbers."""
    missing = [column for column in CSV_COLUMNS[:-1] if column not in frame.columns]
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
