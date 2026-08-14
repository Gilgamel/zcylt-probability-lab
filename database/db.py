"""SQLAlchemy engine, transactional sessions, seeding, and legacy migration."""

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import MetaData, Table, create_engine, event, inspect, select, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from config.settings import DATABASE_URL


class Base(DeclarativeBase):
    """Declarative model base."""


engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 30},
    pool_pre_ping=True,
)


@event.listens_for(engine, "connect")
def configure_sqlite(dbapi_connection: object, _: object) -> None:
    """Configure SQLite integrity, durability, and lock waiting."""
    cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=FULL")
    cursor.execute("PRAGMA busy_timeout=30000")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Provide a session that commits on success and rolls back on failure."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _seed_reference_data(session: Session) -> None:
    """Seed categories, items, displayed targets, and configurable defaults."""
    from config.settings import (
        CATEGORIES,
        DEFAULTS,
        DISPLAYED_PROBABILITIES,
        ITEMS_BY_CATEGORY,
    )
    from database.models import Category, Item, ProbabilityTarget, Setting

    for category_type, name in CATEGORIES.items():
        category = session.scalar(select(Category).where(Category.category_type == category_type))
        if category is None:
            category = Category(name=name, category_type=category_type)
            session.add(category)
            session.flush()
        existing_items = set(session.scalars(select(Item.name).where(Item.category_id == category.id)))
        for item_name in ITEMS_BY_CATEGORY[category_type]:
            if item_name not in existing_items:
                session.add(Item(category_id=category.id, name=item_name, active=True))

    session.flush()
    for category_type, targets in DISPLAYED_PROBABILITIES.items():
        category = session.scalar(select(Category).where(Category.category_type == category_type))
        if category is None:
            continue
        for quality, probability in targets.items():
            target = session.scalar(select(ProbabilityTarget).where(
                ProbabilityTarget.category_id == category.id,
                ProbabilityTarget.item_id.is_(None),
                ProbabilityTarget.level.is_(None),
                ProbabilityTarget.quality == quality,
            ))
            if target is None:
                session.add(ProbabilityTarget(
                    category_id=category.id,
                    quality=quality,
                    displayed_probability=probability,
                    source_note="游戏界面显示概率；保留原始显示值，不做归一化。",
                ))

    for key, value in DEFAULTS.items():
        if session.get(Setting, key) is None:
            session.add(Setting(key=key, value=value))


def _migrate_legacy_material_logs(session: Session) -> None:
    """Copy legacy material rows into Observation once without deleting raw tables."""
    from config.settings import MATERIAL_PRODUCTION
    from database.models import Category, Item, Observation, Setting

    marker = session.get(Setting, "legacy_material_migration_v1")
    table_names = set(inspect(engine).get_table_names())
    if marker is not None or not {"materials", "production_logs"}.issubset(table_names):
        return

    metadata = MetaData()
    materials = Table("materials", metadata, autoload_with=engine)
    logs = Table("production_logs", metadata, autoload_with=engine)
    category = session.scalar(select(Category).where(Category.category_type == MATERIAL_PRODUCTION))
    if category is None:
        return
    item_ids = {
        item.name: item.id
        for item in session.scalars(select(Item).where(Item.category_id == category.id))
    }
    rows = session.execute(
        select(
            logs.c.datetime,
            materials.c.name,
            logs.c.skill_level,
            logs.c.quantity,
            logs.c.red_quantity,
            logs.c.remark,
        ).select_from(logs.join(materials, logs.c.material_id == materials.c.id))
    ).all()
    for row in rows:
        item_id = item_ids.get(row.name)
        if item_id is not None:
            session.add(Observation(
                observed_at=row.datetime,
                category_id=category.id,
                item_id=item_id,
                level=row.skill_level,
                attempt_count=row.quantity,
                orange_count=row.red_quantity,
                remark=row.remark or "",
            ))
    session.add(Setting(key="legacy_material_migration_v1", value=str(len(rows))))


def init_database() -> None:
    """Create the V1.1 schema, seed reference data, and preserve legacy observations."""
    import database.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    # Lightweight additive migration for databases created before bird-session
    # grouping was introduced. SQLAlchemy executes the DDL; raw sqlite3 is not used.
    observation_columns = {
        column["name"] for column in inspect(engine).get_columns("observations")
    }
    if "session_key" not in observation_columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE observations ADD COLUMN session_key VARCHAR(64)"))
            connection.execute(text("CREATE INDEX IF NOT EXISTS ix_observations_session_key ON observations (session_key)"))
    with session_scope() as session:
        _seed_reference_data(session)
        session.flush()
        _migrate_legacy_material_logs(session)
