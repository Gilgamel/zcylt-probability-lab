"""Repository layer for persistence and tabular queries."""

from datetime import datetime
from typing import Any

import pandas as pd
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from database.models import Material, ProductionLog, Setting


class ProbabilityRepository:
    """Encapsulate all application database access."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def materials(self) -> list[Material]:
        return list(self.session.scalars(select(Material).order_by(Material.id)))

    def material_by_name(self, name: str) -> Material | None:
        return self.session.scalar(select(Material).where(Material.name == name))

    def add_log(
        self,
        material_name: str,
        skill_level: int,
        quantity: int,
        red_quantity: int,
        observed_at: datetime | None = None,
        remark: str = "",
    ) -> ProductionLog:
        material = self.material_by_name(material_name)
        if material is None:
            raise ValueError(f"未知材料：{material_name}")
        log = ProductionLog(
            material_id=material.id,
            skill_level=skill_level,
            quantity=quantity,
            red_quantity=red_quantity,
            datetime=observed_at or datetime.now(),
            remark=remark.strip(),
        )
        self.session.add(log)
        self.session.flush()
        return log

    def update_log(self, log_id: int, **values: Any) -> ProductionLog:
        log = self.session.get(ProductionLog, log_id)
        if log is None:
            raise ValueError(f"记录 {log_id} 不存在")
        if "material" in values:
            material = self.material_by_name(str(values.pop("material")))
            if material is None:
                raise ValueError("未知材料")
            log.material_id = material.id
        for key in ("datetime", "skill_level", "quantity", "red_quantity", "remark"):
            if key in values:
                setattr(log, key, values[key])
        self.session.flush()
        return log

    def delete_log(self, log_id: int) -> bool:
        result = self.session.execute(delete(ProductionLog).where(ProductionLog.id == log_id))
        return bool(result.rowcount)

    def logs_dataframe(self) -> pd.DataFrame:
        statement = (
            select(
                ProductionLog.id,
                ProductionLog.datetime,
                Material.name.label("material"),
                ProductionLog.skill_level,
                ProductionLog.quantity,
                ProductionLog.red_quantity,
                ProductionLog.remark,
            )
            .join(Material)
            .order_by(ProductionLog.datetime.desc(), ProductionLog.id.desc())
        )
        rows = self.session.execute(statement).mappings().all()
        return pd.DataFrame(rows, columns=[
            "id", "datetime", "material", "skill_level", "quantity", "red_quantity", "remark"
        ])

    def get_setting(self, key: str, fallback: str = "") -> str:
        setting = self.session.get(Setting, key)
        return setting.value if setting else fallback

    def set_setting(self, key: str, value: str) -> None:
        setting = self.session.get(Setting, key)
        if setting is None:
            self.session.add(Setting(key=key, value=value))
        else:
            setting.value = value
