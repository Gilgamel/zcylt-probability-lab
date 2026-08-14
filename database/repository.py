"""Repository layer for unified observations and application metadata."""

import json
from datetime import datetime
from typing import Any

import pandas as pd
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from config.settings import MATERIAL_PRODUCTION
from database.models import (
    Category,
    Item,
    Observation,
    ProbabilityTarget,
    Setting,
    SimulationRun,
)


OBSERVATION_COLUMNS = [
    "id",
    "observed_at",
    "category",
    "category_type",
    "item",
    "level",
    "attempt_count",
    "green_count",
    "blue_count",
    "purple_count",
    "orange_count",
    "unaccounted_count",
    "session_key",
    "remark",
]


class ProbabilityRepository:
    """Encapsulate database access for every supported game category."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def categories(self) -> list[Category]:
        """Return all categories in seed order."""
        return list(self.session.scalars(select(Category).order_by(Category.id)))

    def category_by_type(self, category_type: str) -> Category | None:
        """Find one category by its stable type identifier."""
        return self.session.scalar(select(Category).where(Category.category_type == category_type))

    def items(self, category_type: str, active_only: bool = True) -> list[Item]:
        """Return items belonging to a category."""
        statement = select(Item).join(Category).where(Category.category_type == category_type)
        if active_only:
            statement = statement.where(Item.active.is_(True))
        return list(self.session.scalars(statement.order_by(Item.id)))

    def item_by_name(self, category_type: str, name: str) -> Item | None:
        """Find an item by category and name."""
        return self.session.scalar(
            select(Item).join(Category).where(
                Category.category_type == category_type,
                Item.name == name,
            )
        )

    def displayed_probabilities(
        self,
        category_type: str,
        item_name: str | None = None,
        level: int | None = None,
    ) -> dict[str, float]:
        """Load official displayed probabilities without normalization."""
        category = self.category_by_type(category_type)
        if category is None:
            return {}
        item = self.item_by_name(category_type, item_name) if item_name else None
        statement = select(ProbabilityTarget).where(
            ProbabilityTarget.category_id == category.id,
            ProbabilityTarget.item_id.is_(item.id if item else None),
            ProbabilityTarget.level.is_(level),
        )
        targets = list(self.session.scalars(statement))
        if not targets and (item is not None or level is not None):
            targets = list(self.session.scalars(select(ProbabilityTarget).where(
                ProbabilityTarget.category_id == category.id,
                ProbabilityTarget.item_id.is_(None),
                ProbabilityTarget.level.is_(None),
            )))
        return {target.quality: target.displayed_probability for target in targets}

    def add_observation(
        self,
        category_type: str,
        item_name: str,
        level: int,
        attempt_count: int,
        observed_at: datetime | None = None,
        green_count: int = 0,
        blue_count: int = 0,
        purple_count: int = 0,
        orange_count: int = 0,
        unaccounted_count: int = 0,
        session_key: str | None = None,
        remark: str = "",
    ) -> Observation:
        """Persist one validated raw observation batch."""
        category = self.category_by_type(category_type)
        item = self.item_by_name(category_type, item_name)
        if category is None or item is None:
            raise ValueError(f"未知分类或项目：{category_type} / {item_name}")
        observation = Observation(
            observed_at=observed_at or datetime.now(),
            category_id=category.id,
            item_id=item.id,
            level=level,
            attempt_count=attempt_count,
            green_count=green_count,
            blue_count=blue_count,
            purple_count=purple_count,
            orange_count=orange_count,
            unaccounted_count=unaccounted_count,
            session_key=session_key,
            remark=remark.strip(),
        )
        self.session.add(observation)
        self.session.flush()
        return observation

    def add_log(
        self,
        material_name: str,
        skill_level: int,
        quantity: int,
        red_quantity: int,
        observed_at: datetime | None = None,
        remark: str = "",
    ) -> Observation:
        """Compatibility wrapper that stores old material input in Observation."""
        return self.add_observation(
            MATERIAL_PRODUCTION,
            material_name,
            skill_level,
            quantity,
            observed_at,
            orange_count=red_quantity,
            remark=remark,
        )

    def update_observation(self, observation_id: int, **values: Any) -> Observation:
        """Update an observation while retaining its identity."""
        observation = self.session.get(Observation, observation_id)
        if observation is None:
            raise ValueError(f"记录 {observation_id} 不存在")
        category_type = values.pop("category_type", None)
        item_name = values.pop("item", None)
        if category_type is not None or item_name is not None:
            current_category = self.session.get(Category, observation.category_id)
            effective_type = category_type or (current_category.category_type if current_category else "")
            effective_name = item_name or self.session.get(Item, observation.item_id).name
            category = self.category_by_type(effective_type)
            item = self.item_by_name(effective_type, effective_name)
            if category is None or item is None:
                raise ValueError("未知分类或项目")
            observation.category_id = category.id
            observation.item_id = item.id
        allowed = {
            "observed_at", "level", "attempt_count", "green_count", "blue_count",
            "purple_count", "orange_count", "unaccounted_count", "remark",
            "session_key",
        }
        for key, value in values.items():
            if key in allowed:
                setattr(observation, key, value)
        self.session.flush()
        return observation

    def update_log(self, log_id: int, **values: Any) -> Observation:
        """Compatibility wrapper for material record editing."""
        translated = {
            "item": values.pop("material", None),
            "level": values.pop("skill_level", None),
            "attempt_count": values.pop("quantity", None),
            "orange_count": values.pop("red_quantity", None),
            "observed_at": values.pop("datetime", None),
            **values,
        }
        return self.update_observation(
            log_id,
            category_type=MATERIAL_PRODUCTION,
            **{key: value for key, value in translated.items() if value is not None},
        )

    def delete_observation(self, observation_id: int) -> bool:
        """Delete one observation by primary key."""
        result = self.session.execute(delete(Observation).where(Observation.id == observation_id))
        return bool(result.rowcount)

    def delete_log(self, log_id: int) -> bool:
        """Compatibility wrapper for deleting a material record."""
        return self.delete_observation(log_id)

    def observations_dataframe(self, category_type: str | None = None) -> pd.DataFrame:
        """Return observations as a stable, export-ready DataFrame."""
        statement = (
            select(
                Observation.id,
                Observation.observed_at,
                Category.name.label("category"),
                Category.category_type,
                Item.name.label("item"),
                Observation.level,
                Observation.attempt_count,
                Observation.green_count,
                Observation.blue_count,
                Observation.purple_count,
                Observation.orange_count,
                Observation.unaccounted_count,
                Observation.session_key,
                Observation.remark,
            )
            .join(Category, Observation.category_id == Category.id)
            .join(Item, Observation.item_id == Item.id)
            .order_by(Observation.observed_at.desc(), Observation.id.desc())
        )
        if category_type:
            statement = statement.where(Category.category_type == category_type)
        rows = self.session.execute(statement).mappings().all()
        frame = pd.DataFrame(rows, columns=OBSERVATION_COLUMNS)
        frame["observed_at"] = pd.to_datetime(frame["observed_at"])
        return frame

    def logs_dataframe(self) -> pd.DataFrame:
        """Return legacy-shaped material data backed by unified observations."""
        frame = self.observations_dataframe(MATERIAL_PRODUCTION)
        if frame.empty:
            return pd.DataFrame(columns=[
                "id", "datetime", "material", "skill_level", "quantity", "red_quantity", "remark"
            ])
        return frame.rename(columns={
            "observed_at": "datetime",
            "item": "material",
            "level": "skill_level",
            "attempt_count": "quantity",
            "orange_count": "red_quantity",
        })[["id", "datetime", "material", "skill_level", "quantity", "red_quantity", "remark"]]

    def save_simulation_run(
        self,
        category_type: str,
        model_name: str,
        probability: float,
        trial_count: int,
        simulation_runs: int,
        random_seed: int | None,
        result: dict[str, Any],
        item_name: str | None = None,
    ) -> SimulationRun:
        """Persist reproducible simulation metadata and compact result summary."""
        category = self.category_by_type(category_type)
        item = self.item_by_name(category_type, item_name) if item_name else None
        if category is None:
            raise ValueError("未知分类")
        run = SimulationRun(
            category_id=category.id,
            item_id=item.id if item else None,
            model_name=model_name,
            probability=probability,
            trial_count=trial_count,
            simulation_runs=simulation_runs,
            random_seed=random_seed,
            result_json=json.dumps(result, ensure_ascii=False),
        )
        self.session.add(run)
        self.session.flush()
        return run

    def get_setting(self, key: str, fallback: str = "") -> str:
        """Read a setting or return a fallback."""
        setting = self.session.get(Setting, key)
        return setting.value if setting else fallback

    def set_setting(self, key: str, value: str) -> None:
        """Insert or update a setting."""
        setting = self.session.get(Setting, key)
        if setting is None:
            self.session.add(Setting(key=key, value=value))
        else:
            setting.value = value
