"""Application-local calendar date tests."""

from datetime import date, datetime, timezone

import pandas as pd

from config.timezone import APPLICATION_TIMEZONE_NAME, application_now, application_today
from services.analysis import recent_attempt_counts


def test_toronto_date_does_not_roll_over_with_utc_server() -> None:
    utc_after_midnight = datetime(2026, 8, 26, 1, 30, tzinfo=timezone.utc)
    assert APPLICATION_TIMEZONE_NAME == "America/Toronto"
    assert application_today(utc_after_midnight) == date(2026, 8, 25)
    local = application_now(utc_after_midnight)
    assert (local.month, local.day, local.hour) == (8, 25, 21)


def test_recent_counts_use_explicit_toronto_calendar_date() -> None:
    daily = pd.DataFrame([
        {"date": "2026-08-24", "category": "马厩", "attempt_count": 8},
        {"date": "2026-08-25", "category": "官匠营", "attempt_count": 18},
        {"date": "2026-08-25", "category": "灵禽院", "attempt_count": 5},
        {"date": "2026-08-26", "category": "官匠营", "attempt_count": 18},
    ])

    today_count, week_count, month_count, today_rows = recent_attempt_counts(
        daily, date(2026, 8, 25)
    )

    assert today_count == 23
    assert week_count == 31
    assert month_count == 31
    assert set(today_rows["category"]) == {"官匠营", "灵禽院"}
