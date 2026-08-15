"""Neon PostgreSQL engine, health checks, sessions, and safe initialization."""

from __future__ import annotations

import os
import time
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass

import streamlit as st
from loguru import logger
from sqlalchemy import Engine, create_engine, select, text
from sqlalchemy.exc import IntegrityError, InterfaceError, OperationalError, SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class DatabaseConfigurationError(RuntimeError):
    """Raised when no valid PostgreSQL connection is configured."""


class DatabaseUnavailableError(RuntimeError):
    """Raised when the configured PostgreSQL database cannot be reached."""


class Base(DeclarativeBase):
    """Declarative model base."""


@dataclass(frozen=True)
class DatabaseHealth:
    """Credential-free database availability result."""

    available: bool
    message: str


def _streamlit_secret() -> str:
    """Read DATABASE_URL from Streamlit Secrets without requiring a secrets file."""
    try:
        return str(st.secrets.get("DATABASE_URL", "")).strip()
    except Exception:
        return ""


def _normalize_postgresql_url(value: str) -> str:
    """Normalize common PostgreSQL URLs to SQLAlchemy's psycopg driver."""
    url = value.strip()
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url.removeprefix("postgres://")
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url.removeprefix("postgresql://")
    if not url.startswith("postgresql+psycopg://"):
        raise DatabaseConfigurationError(
            "DATABASE_URL 必须是 postgresql+psycopg:// 格式的 PostgreSQL 地址。"
        )
    return url


def get_database_url() -> str:
    """Return the configured Neon/PostgreSQL URL, never a local fallback."""
    value = _streamlit_secret() or os.environ.get("DATABASE_URL", "").strip()
    if not value:
        raise DatabaseConfigurationError(
            "尚未配置 DATABASE_URL。请在 Streamlit Secrets 或环境变量中配置 Neon PostgreSQL。"
        )
    return _normalize_postgresql_url(value)


@st.cache_resource(show_spinner=False)
def _cached_engine(database_url: str) -> Engine:
    """Create one process-wide connection pool; sessions are never cached."""
    return create_engine(
        database_url,
        pool_pre_ping=True,
        pool_recycle=300,
        pool_size=5,
        max_overflow=5,
        pool_timeout=20,
        connect_args={"connect_timeout": 15},
    )


def get_engine() -> Engine:
    """Return the cached PostgreSQL engine for the current configuration."""
    return _cached_engine(get_database_url())


def get_session() -> Session:
    """Create a new short-lived SQLAlchemy session."""
    factory = sessionmaker(
        bind=get_engine(), class_=Session, expire_on_commit=False, autoflush=False
    )
    return factory()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Commit one unit of work, rolling the entire transaction back on error."""
    session = get_session()
    try:
        yield session
        session.commit()
    except (OperationalError, InterfaceError) as exc:
        session.rollback()
        logger.error("PostgreSQL session failed: {}", type(exc).__name__)
        raise DatabaseUnavailableError("数据库暂时无法连接，请稍后重试。") from exc
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _seed_reference_data(session: Session) -> None:
    """Insert missing reference rows without overwriting user data."""
    from config.domain import (
        CATEGORIES,
        DEFAULTS,
        DISPLAYED_PROBABILITIES,
        ITEMS_BY_CATEGORY,
        SKILL_PROGRESSION_SEEDS,
    )
    from database.models import (
        Category,
        Item,
        ProbabilityTarget,
        Setting,
        SkillProgression,
    )

    for category_type, name in CATEGORIES.items():
        category = session.scalar(
            select(Category).where(Category.category_type == category_type)
        )
        if category is None:
            category = Category(name=name, category_type=category_type, active=True)
            session.add(category)
            session.flush()
        existing_items = set(
            session.scalars(select(Item.name).where(Item.category_id == category.id))
        )
        for item_name in ITEMS_BY_CATEGORY[category_type]:
            if item_name not in existing_items:
                session.add(Item(category_id=category.id, name=item_name, active=True))

    session.flush()
    for category_type, targets in DISPLAYED_PROBABILITIES.items():
        category = session.scalar(
            select(Category).where(Category.category_type == category_type)
        )
        if category is None:
            continue
        for quality, probability in targets.items():
            target = session.scalar(
                select(ProbabilityTarget).where(
                    ProbabilityTarget.category_id == category.id,
                    ProbabilityTarget.item_id.is_(None),
                    ProbabilityTarget.level.is_(None),
                    ProbabilityTarget.quality == quality,
                )
            )
            if target is None:
                session.add(
                    ProbabilityTarget(
                        category_id=category.id,
                        quality=quality,
                        displayed_probability=probability,
                        source_note="游戏界面显示概率；保留原始显示值，不做归一化。",
                        active=True,
                    )
                )

    for key, value in DEFAULTS.items():
        if session.get(Setting, key) is None:
            session.add(Setting(key=key, value=value))

    for from_level, to_level, required_proficiency in SKILL_PROGRESSION_SEEDS:
        progression = session.scalar(
            select(SkillProgression).where(
                SkillProgression.from_level == from_level,
                SkillProgression.to_level == to_level,
            )
        )
        if progression is None:
            session.add(
                SkillProgression(
                    from_level=from_level,
                    to_level=to_level,
                    required_proficiency=required_proficiency,
                )
            )


def test_connection(engine: Engine | None = None) -> bool:
    """Test once and retry once to tolerate a Neon compute wake-up."""
    target = engine or get_engine()
    for attempt in range(2):
        try:
            with target.connect() as connection:
                connection.execute(text("SELECT 1"))
            return True
        except SQLAlchemyError:
            if attempt:
                raise
            target.dispose()
            time.sleep(1)
    return False


def initialize_database(engine: Engine | None = None) -> None:
    """Create only missing tables and idempotently seed reference data."""
    import database.models  # noqa: F401

    target = engine or get_engine()
    try:
        test_connection(target)
        Base.metadata.create_all(bind=target, checkfirst=True)
        factory = sessionmaker(bind=target, class_=Session, expire_on_commit=False)
        try:
            with factory.begin() as session:
                _seed_reference_data(session)
        except IntegrityError:
            # A parallel cold start may have inserted the same unique seeds.
            # Retry once after that transaction becomes visible.
            with factory.begin() as session:
                _seed_reference_data(session)
    except DatabaseConfigurationError:
        raise
    except SQLAlchemyError as exc:
        logger.error("PostgreSQL initialization failed: {}", type(exc).__name__)
        raise DatabaseUnavailableError("数据库暂时无法连接，请稍后重试。") from exc


def check_database_health() -> DatabaseHealth:
    """Return a safe status that never includes credentials or stack traces."""
    try:
        test_connection()
    except DatabaseConfigurationError as exc:
        return DatabaseHealth(False, str(exc))
    except Exception as exc:
        logger.error("PostgreSQL health check failed: {}", type(exc).__name__)
        return DatabaseHealth(False, "数据库暂时无法连接，请稍后重试。")
    return DatabaseHealth(True, "Connected")


# Compatibility name used by existing page initialization code.
init_database = initialize_database
