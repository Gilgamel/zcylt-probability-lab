"""SQLAlchemy engine and session lifecycle."""

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from config.settings import DATABASE_URL


class Base(DeclarativeBase):
    """Declarative model base."""


engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,
)


@event.listens_for(engine, "connect")
def enable_sqlite_foreign_keys(dbapi_connection: object, _: object) -> None:
    """Enable referential integrity for each SQLite connection."""
    cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Provide a transactional session."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_database() -> None:
    """Create tables and seed required application values."""
    from config.settings import DEFAULTS, MATERIALS
    from database.models import Material, Setting

    Base.metadata.create_all(bind=engine)
    with session_scope() as session:
        names = set(session.scalars(Material.__table__.select().with_only_columns(Material.name)))
        session.add_all(Material(name=name) for name in MATERIALS if name not in names)
        for key, value in DEFAULTS.items():
            if session.get(Setting, key) is None:
                session.add(Setting(key=key, value=value))
