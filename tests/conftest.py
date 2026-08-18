"""Shared PostgreSQL integration fixtures."""

from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from database.db import (
    DatabaseUnavailableError,
    _normalize_postgresql_url,
    initialize_database,
)


@pytest.fixture
def postgres_factory() -> sessionmaker[Session]:
    """Use only an explicitly named test database; never reuse app production secrets."""
    raw_value = os.environ.get("TEST_DATABASE_URL", "").strip()
    if not raw_value:
        pytest.skip("TEST_DATABASE_URL 未配置；跳过 PostgreSQL 集成测试")
    value = _normalize_postgresql_url(raw_value)
    database_name = (make_url(value).database or "").lower()
    explicit_role = os.environ.get("TEST_DATABASE_ROLE", "").strip().lower()
    if "test" not in database_name and explicit_role != "development":
        pytest.fail(
            "TEST_DATABASE_URL 的数据库名称必须包含 test；仅在明确的 Neon Development "
            "验收中可同时设置 TEST_DATABASE_ROLE=development"
        )
    engine = create_engine(value, pool_pre_ping=True)
    try:
        initialize_database(engine)
    except DatabaseUnavailableError:
        engine.dispose()
        pytest.skip("Neon development 暂时不可达；跳过 PostgreSQL 集成测试")
    factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    yield factory
    engine.dispose()
