"""Repository layer; Streamlit pages never issue ORM queries directly."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

import pandas as pd
from sqlalchemy import and_, delete, func, or_, select, text
from sqlalchemy.orm import Session

from config.domain import BIRD_RANDOM, HORSE_SEARCH, MATERIAL_PRODUCTION
from database.models import (
    Category,
    Item,
    Observation,
    ProbabilityTarget,
    Setting,
    SkillProgression,
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
    "session_id",
    "remark",
    "created_at",
    "updated_at",
]


class CategoryRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def all(self, active_only: bool = True) -> list[Category]:
        statement = select(Category)
        if active_only:
            statement = statement.where(Category.active.is_(True))
        return list(self.session.scalars(statement.order_by(Category.id)))

    def by_type(self, category_type: str) -> Category | None:
        return self.session.scalar(
            select(Category).where(Category.category_type == category_type)
        )

    def create(self, name: str, category_type: str, active: bool = True) -> Category:
        category = Category(name=name, category_type=category_type, active=active)
        self.session.add(category)
        self.session.flush()
        return category

    def update(self, category_id: int, **values: Any) -> Category:
        category = self.session.get(Category, category_id)
        if category is None:
            raise ValueError(f"分类 {category_id} 不存在")
        for key in ("name", "category_type", "active"):
            if key in values:
                setattr(category, key, values[key])
        self.session.flush()
        return category

    def delete(self, category_id: int) -> bool:
        category = self.session.get(Category, category_id)
        if category is None:
            return False
        self.session.delete(category)
        self.session.flush()
        return True

    def dataframe(self) -> pd.DataFrame:
        rows = [
            {"category_type": row.category_type, "name": row.name, "active": row.active}
            for row in self.all(active_only=False)
        ]
        return pd.DataFrame(rows, columns=["category_type", "name", "active"])


class ItemRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def all_for_category(
        self, category_type: str, active_only: bool = True
    ) -> list[Item]:
        statement = select(Item).join(Category).where(
            Category.category_type == category_type
        )
        if active_only:
            statement = statement.where(Item.active.is_(True))
        return list(self.session.scalars(statement.order_by(Item.id)))

    def by_name(self, category_type: str, name: str) -> Item | None:
        return self.session.scalar(
            select(Item).join(Category).where(
                Category.category_type == category_type, Item.name == name
            )
        )

    def create(self, category_id: int, name: str, active: bool = True) -> Item:
        item = Item(category_id=category_id, name=name, active=active)
        self.session.add(item)
        self.session.flush()
        return item

    def update(self, item_id: int, **values: Any) -> Item:
        item = self.session.get(Item, item_id)
        if item is None:
            raise ValueError(f"项目 {item_id} 不存在")
        for key in ("name", "active"):
            if key in values:
                setattr(item, key, values[key])
        self.session.flush()
        return item

    def delete(self, item_id: int) -> bool:
        item = self.session.get(Item, item_id)
        if item is None:
            return False
        self.session.delete(item)
        self.session.flush()
        return True

    def dataframe(self) -> pd.DataFrame:
        rows = self.session.execute(
            select(
                Category.category_type,
                Item.name,
                Item.active,
            )
            .join(Category, Item.category_id == Category.id)
            .order_by(Category.id, Item.id)
        ).mappings()
        return pd.DataFrame(rows, columns=["category_type", "name", "active"])


class ObservationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    @staticmethod
    def _as_date(value: date | datetime | None) -> date:
        if value is None:
            return date.today()
        return value.date() if isinstance(value, datetime) else value

    def add(
        self,
        category_type: str,
        item_name: str,
        level: int,
        attempt_count: int,
        observed_at: date | datetime | None = None,
        green_count: int = 0,
        blue_count: int = 0,
        purple_count: int = 0,
        orange_count: int = 0,
        unaccounted_count: int = 0,
        session_id: UUID | str | None = None,
        remark: str = "",
        observation_id: int | None = None,
    ) -> Observation:
        category = CategoryRepository(self.session).by_type(category_type)
        item = ItemRepository(self.session).by_name(category_type, item_name)
        if category is None or item is None:
            raise ValueError(f"未知分类或项目：{category_type} / {item_name}")
        observation = Observation(
            id=observation_id,
            session_id=UUID(str(session_id)) if session_id else uuid4(),
            observed_at=self._as_date(observed_at),
            category_id=category.id,
            item_id=item.id,
            level=level,
            attempt_count=attempt_count,
            green_count=green_count,
            blue_count=blue_count,
            purple_count=purple_count,
            orange_count=orange_count,
            unaccounted_count=unaccounted_count,
            remark=remark.strip(),
        )
        self.session.add(observation)
        self.session.flush()
        return observation

    def add_material(
        self,
        material_name: str,
        skill_level: int,
        quantity: int,
        orange_quantity: int,
        observed_at: date | datetime | None = None,
        remark: str = "",
    ) -> Observation:
        return self.add(
            MATERIAL_PRODUCTION,
            material_name,
            skill_level,
            quantity,
            observed_at,
            orange_count=orange_quantity,
            remark=remark,
        )

    def update(self, observation_id: int, **values: Any) -> Observation:
        observation = self.session.get(Observation, observation_id)
        if observation is None:
            raise ValueError(f"记录 {observation_id} 不存在")
        category_type = values.pop("category_type", None)
        item_name = values.pop("item", None)
        if category_type is not None or item_name is not None:
            current_category = self.session.get(Category, observation.category_id)
            current_item = self.session.get(Item, observation.item_id)
            effective_type = category_type or (
                current_category.category_type if current_category else ""
            )
            effective_name = item_name or (current_item.name if current_item else "")
            category = CategoryRepository(self.session).by_type(effective_type)
            item = ItemRepository(self.session).by_name(effective_type, effective_name)
            if category is None or item is None:
                raise ValueError("未知分类或项目")
            observation.category_id = category.id
            observation.item_id = item.id
        allowed = {
            "observed_at",
            "level",
            "attempt_count",
            "green_count",
            "blue_count",
            "purple_count",
            "orange_count",
            "unaccounted_count",
            "remark",
            "session_id",
        }
        for key, value in values.items():
            if key in allowed:
                if key == "observed_at":
                    value = self._as_date(value)
                elif key == "session_id" and value is not None:
                    value = UUID(str(value))
                setattr(observation, key, value)
        self.session.flush()
        return observation

    def delete(self, observation_id: int) -> bool:
        result = self.session.execute(
            delete(Observation).where(Observation.id == observation_id)
        )
        return bool(result.rowcount)

    def by_id(self, observation_id: int) -> Observation | None:
        return self.session.get(Observation, observation_id)

    def reset_primary_key_sequence(self) -> None:
        """Advance PostgreSQL's identity sequence after ID-preserving restore."""
        self.session.execute(
            text(
                "SELECT setval(pg_get_serial_sequence('observations', 'id'), "
                "COALESCE(MAX(id), 1), MAX(id) IS NOT NULL) FROM observations"
            )
        )

    def dataframe(
        self,
        category_type: str | None = None,
        item_name: str | None = None,
        level: int | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        search_text: str | None = None,
    ) -> pd.DataFrame:
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
                Observation.session_id,
                Observation.remark,
                Observation.created_at,
                Observation.updated_at,
            )
            .join(Category, Observation.category_id == Category.id)
            .join(Item, Observation.item_id == Item.id)
            .order_by(Observation.observed_at.desc(), Observation.id.desc())
        )
        if category_type:
            statement = statement.where(Category.category_type == category_type)
        if item_name:
            statement = statement.where(Item.name == item_name)
        if level is not None:
            statement = statement.where(Observation.level == level)
        if start_date:
            statement = statement.where(Observation.observed_at >= start_date)
        if end_date:
            statement = statement.where(Observation.observed_at <= end_date)
        if search_text:
            pattern = f"%{search_text}%"
            statement = statement.where(
                Item.name.ilike(pattern) | Observation.remark.ilike(pattern)
            )
        rows = self.session.execute(statement).mappings().all()
        frame = pd.DataFrame(rows, columns=OBSERVATION_COLUMNS)
        frame["observed_at"] = pd.to_datetime(frame["observed_at"])
        return frame

    def material_dataframe(self) -> pd.DataFrame:
        frame = self.dataframe(MATERIAL_PRODUCTION)
        if frame.empty:
            return pd.DataFrame(
                columns=[
                    "id", "datetime", "material", "skill_level", "quantity",
                    "red_quantity", "remark",
                ]
            )
        return frame.rename(
            columns={
                "observed_at": "datetime", "item": "material",
                "level": "skill_level", "attempt_count": "quantity",
                "orange_count": "red_quantity",
            }
        )[["id", "datetime", "material", "skill_level", "quantity", "red_quantity", "remark"]]

    def totals_by_category(self) -> pd.DataFrame:
        rows = self.session.execute(
            select(
                Category.name.label("category"), Category.category_type,
                func.count(Observation.id).label("records"),
                func.coalesce(func.sum(Observation.attempt_count), 0).label("attempts"),
                func.coalesce(func.sum(Observation.orange_count), 0).label("orange"),
            )
            .outerjoin(Observation, Observation.category_id == Category.id)
            .where(Category.active.is_(True))
            .group_by(Category.id, Category.name, Category.category_type)
            .order_by(Category.id)
        ).mappings()
        return pd.DataFrame(rows)

    def daily_totals(self) -> pd.DataFrame:
        rows = self.session.execute(
            select(
                Observation.observed_at.label("date"), Category.name.label("category"),
                Category.category_type,
                func.sum(Observation.attempt_count).label("attempt_count"),
                func.sum(Observation.orange_count).label("orange_count"),
            )
            .join(Category, Observation.category_id == Category.id)
            .group_by(
                Observation.observed_at, Category.id, Category.name,
                Category.category_type,
            )
            .order_by(Observation.observed_at)
        ).mappings()
        frame = pd.DataFrame(rows)
        if not frame.empty:
            frame["date"] = pd.to_datetime(frame["date"])
        return frame


class AnalysisRepository:
    """Compact SQL aggregations for Phase 3 statistical analysis.

    Analysis pages receive grouped rows only.  Invalid legacy rows are excluded
    defensively even though current database constraints and validators prevent
    new invalid observations.
    """

    QUALITY_COLUMNS = ("green_count", "blue_count", "purple_count", "orange_count", "unaccounted_count")

    def __init__(self, session: Session) -> None:
        self.session = session

    @staticmethod
    def _valid_observation(category_type: str | None = None):
        quality_total = (
            Observation.green_count + Observation.blue_count
            + Observation.purple_count + Observation.orange_count
            + Observation.unaccounted_count
        )
        base_rules = and_(
            Observation.attempt_count > 0,
            Observation.level > 0,
            Observation.green_count >= 0,
            Observation.blue_count >= 0,
            Observation.purple_count >= 0,
            Observation.orange_count >= 0,
            Observation.unaccounted_count >= 0,
            quality_total <= Observation.attempt_count,
        )
        category_rules = {
            MATERIAL_PRODUCTION: and_(
                Observation.level.in_((9, 10, 11, 12)),
            ),
            HORSE_SEARCH: and_(
                Observation.attempt_count <= 8,
                quality_total == Observation.attempt_count,
            ),
            BIRD_RANDOM: and_(
                Observation.attempt_count == 1,
                Observation.green_count == 0,
                Observation.unaccounted_count == 0,
                Observation.blue_count + Observation.purple_count
                + Observation.orange_count == 1,
            ),
        }
        if category_type is not None:
            return and_(base_rules, category_rules[category_type])
        return and_(
            base_rules,
            or_(*(
                and_(Category.category_type == name, rules)
                for name, rules in category_rules.items()
            )),
        )

    @staticmethod
    def _frame(rows: Any, columns: list[str]) -> pd.DataFrame:
        return pd.DataFrame(list(rows), columns=columns)

    def dashboard_totals(self) -> pd.DataFrame:
        columns = ["category", "category_type", "records", "items_with_data", "attempts", "orange"]
        rows = self.session.execute(
            select(
                Category.name.label("category"),
                Category.category_type,
                func.count(Observation.id).label("records"),
                func.count(func.distinct(Observation.item_id)).label("items_with_data"),
                func.coalesce(func.sum(Observation.attempt_count), 0).label("attempts"),
                func.coalesce(func.sum(Observation.orange_count), 0).label("orange"),
            )
            .outerjoin(
                Observation,
                and_(
                    Observation.category_id == Category.id,
                    self._valid_observation(),
                ),
            )
            .where(Category.active.is_(True))
            .group_by(Category.id, Category.name, Category.category_type)
            .order_by(Category.id)
        ).mappings()
        return self._frame(rows, columns)

    def daily_totals(self) -> pd.DataFrame:
        columns = ["date", "category", "category_type", "attempt_count", "orange_count"]
        rows = self.session.execute(
            select(
                Observation.observed_at.label("date"),
                Category.name.label("category"),
                Category.category_type,
                func.sum(Observation.attempt_count).label("attempt_count"),
                func.sum(Observation.orange_count).label("orange_count"),
            )
            .join(Category, Observation.category_id == Category.id)
            .where(self._valid_observation())
            .group_by(
                Observation.observed_at, Category.id, Category.name,
                Category.category_type,
            )
            .order_by(Observation.observed_at, Category.id)
        ).mappings()
        frame = self._frame(rows, columns)
        if not frame.empty:
            frame["date"] = pd.to_datetime(frame["date"])
        return frame

    def material_summary(
        self, material: str | None = None, level: int | None = None
    ) -> pd.DataFrame:
        columns = ["item", "level", "records", "attempts", "orange"]
        statement = (
            select(
                Item.name.label("item"),
                Observation.level,
                func.count(Observation.id).label("records"),
                func.sum(Observation.attempt_count).label("attempts"),
                func.sum(Observation.orange_count).label("orange"),
            )
            .join(Category, Observation.category_id == Category.id)
            .join(Item, Observation.item_id == Item.id)
            .where(
                Category.category_type == MATERIAL_PRODUCTION,
                Observation.level.in_((9, 10, 11, 12)),
                self._valid_observation(MATERIAL_PRODUCTION),
            )
        )
        if material:
            statement = statement.where(Item.name == material)
        if level is not None:
            statement = statement.where(Observation.level == level)
        rows = self.session.execute(
            statement.group_by(Item.name, Observation.level).order_by(Item.name, Observation.level)
        ).mappings()
        return self._frame(rows, columns)

    def material_daily(
        self, material: str | None = None, level: int | None = None
    ) -> pd.DataFrame:
        columns = ["date", "attempts", "orange"]
        statement = (
            select(
                Observation.observed_at.label("date"),
                func.sum(Observation.attempt_count).label("attempts"),
                func.sum(Observation.orange_count).label("orange"),
            )
            .join(Category, Observation.category_id == Category.id)
            .join(Item, Observation.item_id == Item.id)
            .where(
                Category.category_type == MATERIAL_PRODUCTION,
                Observation.level.in_((9, 10, 11, 12)),
                self._valid_observation(MATERIAL_PRODUCTION),
            )
        )
        if material:
            statement = statement.where(Item.name == material)
        if level is not None:
            statement = statement.where(Observation.level == level)
        rows = self.session.execute(
            statement.group_by(Observation.observed_at).order_by(Observation.observed_at)
        ).mappings()
        frame = self._frame(rows, columns)
        if not frame.empty:
            frame["date"] = pd.to_datetime(frame["date"])
        return frame

    def quality_summary(
        self, category_type: str, item: str | None = None, level: int | None = None
    ) -> pd.DataFrame:
        columns = [
            "records", "attempts", "green", "blue", "purple", "orange", "unaccounted"
        ]
        statement = (
            select(
                func.count(Observation.id).label("records"),
                func.coalesce(func.sum(Observation.attempt_count), 0).label("attempts"),
                func.coalesce(func.sum(Observation.green_count), 0).label("green"),
                func.coalesce(func.sum(Observation.blue_count), 0).label("blue"),
                func.coalesce(func.sum(Observation.purple_count), 0).label("purple"),
                func.coalesce(func.sum(Observation.orange_count), 0).label("orange"),
                func.coalesce(func.sum(Observation.unaccounted_count), 0).label("unaccounted"),
            )
            .join(Category, Observation.category_id == Category.id)
            .join(Item, Observation.item_id == Item.id)
            .where(
                Category.category_type == category_type,
                self._valid_observation(category_type),
            )
        )
        if item:
            statement = statement.where(Item.name == item)
        if level is not None:
            statement = statement.where(Observation.level == level)
        rows = self.session.execute(statement).mappings()
        return self._frame(rows, columns)

    def quality_by_item(
        self, category_type: str, level: int | None = None
    ) -> pd.DataFrame:
        columns = [
            "item", "records", "attempts", "green", "blue", "purple", "orange", "unaccounted"
        ]
        statement = (
            select(
                Item.name.label("item"),
                func.count(Observation.id).label("records"),
                func.sum(Observation.attempt_count).label("attempts"),
                func.sum(Observation.green_count).label("green"),
                func.sum(Observation.blue_count).label("blue"),
                func.sum(Observation.purple_count).label("purple"),
                func.sum(Observation.orange_count).label("orange"),
                func.sum(Observation.unaccounted_count).label("unaccounted"),
            )
            .join(Category, Observation.category_id == Category.id)
            .join(Item, Observation.item_id == Item.id)
            .where(
                Category.category_type == category_type,
                self._valid_observation(category_type),
            )
        )
        if level is not None:
            statement = statement.where(Observation.level == level)
        rows = self.session.execute(
            statement.group_by(Item.name).order_by(Item.name)
        ).mappings()
        return self._frame(rows, columns)

    def session_summary(
        self, category_type: str, item: str | None = None, level: int | None = None
    ) -> pd.DataFrame:
        columns = ["session_id", "searches", "orange"]
        statement = (
            select(
                Observation.session_id,
                func.sum(Observation.attempt_count).label("searches"),
                func.sum(Observation.orange_count).label("orange"),
            )
            .join(Category, Observation.category_id == Category.id)
            .join(Item, Observation.item_id == Item.id)
            .where(
                Category.category_type == category_type,
                self._valid_observation(category_type),
            )
        )
        if item:
            statement = statement.where(Item.name == item)
        if level is not None:
            statement = statement.where(Observation.level == level)
        rows = self.session.execute(
            statement.group_by(Observation.session_id).order_by(Observation.session_id)
        ).mappings()
        return self._frame(rows, columns)

class ProbabilityRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def displayed(
        self,
        category_type: str,
        item_name: str | None = None,
        level: int | None = None,
    ) -> dict[str, float]:
        category = CategoryRepository(self.session).by_type(category_type)
        if category is None:
            return {}
        item = (
            ItemRepository(self.session).by_name(category_type, item_name)
            if item_name
            else None
        )
        statement = select(ProbabilityTarget).where(
            ProbabilityTarget.category_id == category.id,
            ProbabilityTarget.item_id.is_(item.id if item else None),
            ProbabilityTarget.level.is_(level),
            ProbabilityTarget.active.is_(True),
        )
        targets = list(self.session.scalars(statement))
        if not targets and (item is not None or level is not None):
            targets = list(
                self.session.scalars(
                    select(ProbabilityTarget).where(
                        ProbabilityTarget.category_id == category.id,
                        ProbabilityTarget.item_id.is_(None),
                        ProbabilityTarget.level.is_(None),
                        ProbabilityTarget.active.is_(True),
                    )
                )
            )
        return {target.quality: target.displayed_probability for target in targets}

    def all(self) -> list[ProbabilityTarget]:
        return list(self.session.scalars(select(ProbabilityTarget).order_by(ProbabilityTarget.id)))

    def dataframe(self) -> pd.DataFrame:
        item_alias = Item.__table__.alias("target_item")
        rows = self.session.execute(
            select(
                Category.category_type,
                item_alias.c.name.label("item"),
                ProbabilityTarget.level,
                ProbabilityTarget.quality,
                ProbabilityTarget.displayed_probability,
                ProbabilityTarget.source_note,
                ProbabilityTarget.active,
            )
            .join(Category, ProbabilityTarget.category_id == Category.id)
            .outerjoin(item_alias, ProbabilityTarget.item_id == item_alias.c.id)
            .order_by(ProbabilityTarget.id)
        ).mappings()
        return pd.DataFrame(
            rows,
            columns=[
                "category_type",
                "item",
                "level",
                "quality",
                "displayed_probability",
                "source_note",
                "active",
            ],
        )

    def upsert(
        self,
        category_type: str,
        quality: str,
        displayed_probability: float,
        item_name: str | None = None,
        level: int | None = None,
        source_note: str = "",
        active: bool = True,
    ) -> None:
        category = CategoryRepository(self.session).by_type(category_type)
        item = (
            ItemRepository(self.session).by_name(category_type, item_name)
            if item_name
            else None
        )
        if category is None or (item_name and item is None):
            raise ValueError("概率目标引用了未知分类或项目")
        target = self.session.scalar(
            select(ProbabilityTarget).where(
                ProbabilityTarget.category_id == category.id,
                ProbabilityTarget.item_id.is_(item.id if item else None),
                ProbabilityTarget.level.is_(level),
                ProbabilityTarget.quality == quality,
            )
        )
        if target is None:
            target = ProbabilityTarget(
                category_id=category.id,
                item_id=item.id if item else None,
                level=level,
                quality=quality,
                displayed_probability=displayed_probability,
            )
            self.session.add(target)
        target.displayed_probability = displayed_probability
        target.source_note = source_note
        target.active = active


class SettingsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, key: str, fallback: str = "") -> str:
        setting = self.session.get(Setting, key)
        return setting.value if setting else fallback

    def set(self, key: str, value: str) -> None:
        setting = self.session.get(Setting, key)
        if setting is None:
            self.session.add(Setting(key=key, value=value))
        else:
            setting.value = value

    def all(self) -> list[Setting]:
        return list(self.session.scalars(select(Setting).order_by(Setting.key)))

    def dataframe(self) -> pd.DataFrame:
        return pd.DataFrame(
            [{"key": row.key, "value": row.value} for row in self.all()],
            columns=["key", "value"],
        )


class SkillProgressionRepository:
    """Access reference proficiency transitions without applying weights."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def all(self) -> list[SkillProgression]:
        return list(
            self.session.scalars(
                select(SkillProgression).order_by(SkillProgression.from_level)
            )
        )

    def by_transition(
        self, from_level: int, to_level: int
    ) -> SkillProgression | None:
        return self.session.scalar(
            select(SkillProgression).where(
                SkillProgression.from_level == from_level,
                SkillProgression.to_level == to_level,
            )
        )


class SimulationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(
        self,
        category_type: str,
        model_name: str,
        probability: float,
        trial_count: int,
        simulation_runs: int,
        random_seed: int | None,
        result: dict[str, Any],
        item_name: str | None = None,
        level: int | None = None,
    ) -> SimulationRun:
        category = CategoryRepository(self.session).by_type(category_type)
        item = (
            ItemRepository(self.session).by_name(category_type, item_name)
            if item_name
            else None
        )
        if category is None:
            raise ValueError("未知分类")
        run = SimulationRun(
            category_id=category.id,
            item_id=item.id if item else None,
            level=level,
            model_name=model_name,
            probability=probability,
            trial_count=trial_count,
            simulation_runs=simulation_runs,
            random_seed=random_seed,
            result_json=result,
        )
        self.session.add(run)
        self.session.flush()
        return run

    def recent(self, limit: int = 20) -> list[SimulationRun]:
        return list(
            self.session.scalars(
                select(SimulationRun)
                .order_by(SimulationRun.created_at.desc(), SimulationRun.id.desc())
                .limit(limit)
            )
        )

    def dataframe(self, limit: int = 50) -> pd.DataFrame:
        item_alias = Item.__table__.alias("simulation_item")
        rows = self.session.execute(
            select(
                SimulationRun.id,
                SimulationRun.created_at,
                Category.name.label("category"),
                item_alias.c.name.label("item"),
                SimulationRun.model_name,
                SimulationRun.level,
                SimulationRun.probability,
                SimulationRun.trial_count,
                SimulationRun.simulation_runs,
                SimulationRun.random_seed,
                SimulationRun.result_json,
            )
            .join(Category, SimulationRun.category_id == Category.id)
            .outerjoin(item_alias, SimulationRun.item_id == item_alias.c.id)
            .order_by(SimulationRun.created_at.desc(), SimulationRun.id.desc())
            .limit(limit)
        ).mappings()
        return pd.DataFrame(rows)
