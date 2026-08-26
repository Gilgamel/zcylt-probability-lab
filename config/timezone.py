"""Application-local date helpers independent of the server's timezone."""

from __future__ import annotations

import os
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo


APPLICATION_TIMEZONE_NAME = os.environ.get("APP_TIMEZONE", "America/Toronto")
try:
    APPLICATION_TIMEZONE = ZoneInfo(APPLICATION_TIMEZONE_NAME)
except Exception:
    APPLICATION_TIMEZONE_NAME = "America/Toronto"
    APPLICATION_TIMEZONE = ZoneInfo(APPLICATION_TIMEZONE_NAME)


def application_now(now_utc: datetime | None = None) -> datetime:
    """Return a timezone-aware datetime in the configured application zone."""
    current = now_utc or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(APPLICATION_TIMEZONE)


def application_today(now_utc: datetime | None = None) -> date:
    """Return the application-local calendar date."""
    return application_now(now_utc).date()
