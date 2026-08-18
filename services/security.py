"""Fail-closed verification for destructive application actions."""

from __future__ import annotations

import os
import secrets

import streamlit as st


def _configured_delete_password() -> str:
    """Read the deletion password without logging or persisting its value."""
    try:
        streamlit_value = st.secrets.get("DELETE_PASSWORD", "")
    except Exception:
        streamlit_value = ""
    return str(streamlit_value or os.environ.get("DELETE_PASSWORD", ""))


def delete_password_is_configured() -> bool:
    """Return whether deletion can be enabled safely."""
    return bool(_configured_delete_password())


def verify_delete_password(candidate: str) -> bool:
    """Compare passwords in constant time and fail closed when unconfigured."""
    configured = _configured_delete_password()
    return bool(configured) and secrets.compare_digest(candidate, configured)
