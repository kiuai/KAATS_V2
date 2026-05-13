from __future__ import annotations

from datetime import datetime, timezone

import pytz
from croniter import CroniterBadCronError, croniter


def validate_cron(expression: str) -> bool:
    """Return True if expression is a valid 5-field cron string."""
    return croniter.is_valid(expression)


def compute_next_run(expression: str, timezone_str: str, after: datetime) -> datetime:
    """
    Compute the next fire time for a cron expression in the given timezone.
    Returns a naive UTC datetime (no tzinfo) suitable for SQL storage.
    """
    try:
        tz = pytz.timezone(timezone_str)
    except pytz.UnknownTimeZoneError:
        tz = pytz.utc

    # If after is naive, treat as UTC
    if after.tzinfo is None:
        after_aware = pytz.utc.localize(after)
    else:
        after_aware = after.astimezone(pytz.utc)

    after_local = after_aware.astimezone(tz)
    cron = croniter(expression, after_local)
    next_local: datetime = cron.get_next(datetime)

    next_utc = next_local.astimezone(pytz.utc)
    return next_utc.replace(tzinfo=None)
