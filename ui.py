"""Shared Streamlit presentation helpers."""

from collections.abc import Callable

import pandas as pd
import streamlit as st
from loguru import logger

from charts.plotly_chart import apply_theme
from config.settings import LOG_DIR
from database.db import (
    DatabaseConfigurationError,
    DatabaseUnavailableError,
    check_database_health,
    initialize_database,
    session_scope,
)
from database.repository import (
    AnalysisRepository,
    ObservationRepository,
    ProbabilityRepository,
    SimulationRepository,
    SettingsRepository,
)
from services.statistics import SufficiencyThresholds

logger.add(LOG_DIR / "probability_lab.log", rotation="5 MB", retention="14 days")

# Transparent favicon: no emoji and no visible Streamlit logo in the browser tab.
TRANSPARENT_FAVICON = (
    "data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs="
)


def configure_page(title: str) -> None:
    st.set_page_config(
        page_title=f"{title} · ProbabilityLab",
        page_icon=TRANSPARENT_FAVICON,
        layout="wide",
    )
    st.markdown(
        """
        <style>
        [data-testid="stMetric"] {border: 1px solid rgba(128,128,128,.22); padding: 1rem; border-radius: .7rem;}
        .block-container {padding-top: 2rem; padding-bottom: 3rem;}
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_resource
def prepare_database() -> bool:
    initialize_database()
    return True


def load_logs() -> pd.DataFrame:
    prepare_database()
    with session_scope() as session:
        return ObservationRepository(session).material_dataframe()


def load_observations(category_type: str | None = None) -> pd.DataFrame:
    """Load unified observations, optionally restricted to one category."""
    prepare_database()
    with session_scope() as session:
        return ObservationRepository(session).dataframe(category_type)


def load_dashboard_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load SQL-aggregated dashboard totals and daily time series."""
    prepare_database()
    with session_scope() as session:
        repository = AnalysisRepository(session)
        return repository.dashboard_totals(), repository.daily_totals()


def load_material_analysis(
    material: str | None = None,
    level: int | None = None,
    start_date=None,
    end_date=None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load compact material group and daily aggregates from PostgreSQL."""
    prepare_database()
    with session_scope() as session:
        repository = AnalysisRepository(session)
        return (
            repository.material_summary(material, level, start_date, end_date),
            repository.material_daily(material, level, start_date, end_date),
        )


def load_quality_analysis(
    category_type: str,
    item: str | None = None,
    level: int | None = None,
    start_date=None,
    end_date=None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load compact quality, item and session aggregates from PostgreSQL."""
    prepare_database()
    with session_scope() as session:
        repository = AnalysisRepository(session)
        return (
            repository.quality_summary(
                category_type, item, level, start_date, end_date
            ),
            repository.quality_by_item(
                category_type, level, start_date, end_date
            ),
            repository.session_summary(
                category_type, item, level, start_date, end_date
            ),
        )


def save_simulation_run(
    category_type: str,
    model_name: str,
    probability: float,
    trial_count: int,
    simulation_count: int,
    random_seed: int,
    result: dict,
    item_name: str | None = None,
    level: int | None = None,
) -> int:
    """Persist one versioned simulation summary and return its ID."""
    prepare_database()
    with session_scope() as session:
        run = SimulationRepository(session).add(
            category_type,
            model_name,
            probability,
            trial_count,
            simulation_count,
            random_seed,
            result,
            item_name,
            level,
        )
        return run.id


def load_simulation_history(limit: int = 20) -> pd.DataFrame:
    """Load stored simulation metadata and versioned summaries."""
    prepare_database()
    with session_scope() as session:
        return SimulationRepository(session).recent_dataframe(limit)


def get_setting(key: str, fallback: str) -> str:
    prepare_database()
    with session_scope() as session:
        return SettingsRepository(session).get(key, fallback)


def get_displayed_probabilities(category_type: str) -> dict[str, float]:
    """Load raw displayed probability targets from PostgreSQL."""
    prepare_database()
    with session_scope() as session:
        return ProbabilityRepository(session).displayed(category_type)


def show_database_status() -> None:
    """Render a credential-free database health badge."""
    health = check_database_health()
    if health.available:
        st.success("数据库状态：Connected")
    else:
        st.error(f"数据库状态：Unavailable · {health.message}")


def sufficiency_settings() -> tuple[SufficiencyThresholds, float]:
    """Build sample precision configuration from persisted settings."""
    thresholds = SufficiencyThresholds(
        grade_a=float(get_setting("sufficiency_a_moe", "0.005")),
        grade_b=float(get_setting("sufficiency_b_moe", "0.010")),
        grade_c=float(get_setting("sufficiency_c_moe", "0.020")),
    )
    return thresholds, float(get_setting("target_margin_of_error", "0.005"))


def show_chart(figure: object, key: str | None = None) -> None:
    theme = get_setting("theme", "dark")
    st.plotly_chart(apply_theme(figure, theme), width="stretch", key=key)


def page_guard(render: Callable[[], None]) -> None:
    """Render a page with friendly exception handling and persistent logs."""
    try:
        prepare_database()
        render()
    except DatabaseConfigurationError as exc:
        logger.warning("Database configuration is missing or invalid")
        st.error(str(exc))
        st.info(
            "请在 Streamlit Cloud 的 App settings → Secrets 中添加 "
            "DATABASE_URL，或在本地环境变量中配置。数据库操作已禁用。"
        )
    except DatabaseUnavailableError:
        st.error("数据库暂时无法连接，请稍后重试。")
        st.info("Neon 可能正在从休眠状态唤醒；请稍候刷新。数据库操作已禁用。")
    except Exception:  # Streamlit pages must remain usable on failure.
        logger.exception("Page rendering failed")
        st.error("操作未完成。技术详情已写入服务器日志。")
