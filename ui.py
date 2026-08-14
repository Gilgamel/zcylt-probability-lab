"""Shared Streamlit presentation helpers."""

from collections.abc import Callable

import pandas as pd
import streamlit as st
from loguru import logger

from charts.plotly_chart import apply_theme
from config.settings import LOG_DIR
from database.db import init_database, session_scope
from database.repository import ProbabilityRepository
from services.statistics import SufficiencyThresholds

logger.add(LOG_DIR / "probability_lab.log", rotation="5 MB", retention="14 days")


def configure_page(title: str, icon: str = "🎲") -> None:
    st.set_page_config(page_title=f"{title} · ProbabilityLab", page_icon=icon, layout="wide")
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
    init_database()
    return True


def load_logs() -> pd.DataFrame:
    prepare_database()
    with session_scope() as session:
        return ProbabilityRepository(session).logs_dataframe()


def load_observations(category_type: str | None = None) -> pd.DataFrame:
    """Load unified observations, optionally restricted to one category."""
    prepare_database()
    with session_scope() as session:
        return ProbabilityRepository(session).observations_dataframe(category_type)


def get_setting(key: str, fallback: str) -> str:
    prepare_database()
    with session_scope() as session:
        return ProbabilityRepository(session).get_setting(key, fallback)


def get_displayed_probabilities(category_type: str) -> dict[str, float]:
    """Load raw displayed probability targets from SQLite."""
    prepare_database()
    with session_scope() as session:
        return ProbabilityRepository(session).displayed_probabilities(category_type)


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
    except Exception as exc:  # Streamlit pages must remain usable on failure.
        logger.exception("Page rendering failed")
        st.error(f"操作未完成：{exc}")
