"""Cron expression validation, scheduling, and human-readable description."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Final

import pytz
from croniter import CroniterBadCronError, croniter

# Minimum allowed interval between firings (15 minutes per spec)
_MIN_INTERVAL_MINUTES: Final = 15
_WEEKDAY_NAMES: Final = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
_MONTH_NAMES: Final = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


class CronParser:
    """Validates, schedules, and describes 5-field cron expressions."""

    def validate(self, expression: str) -> bool:
        """Return True if the expression is a valid 5-field cron string."""
        return croniter.is_valid(expression)

    def validate_min_interval(self, expression: str) -> bool:
        """
        Return True if the expression fires no more often than every
        _MIN_INTERVAL_MINUTES minutes. Prevents abuse.
        """
        if not self.validate(expression):
            return False
        try:
            now = datetime.now(timezone.utc)
            cron = croniter(expression, now)
            t1: datetime = cron.get_next(datetime)
            t2: datetime = cron.get_next(datetime)
            gap_minutes = (t2 - t1).total_seconds() / 60
            return gap_minutes >= _MIN_INTERVAL_MINUTES
        except Exception:
            return False

    def next_run(self, expression: str, after: datetime | None = None) -> datetime:
        """
        Calculate the next UTC fire time (naive, no tzinfo) for a cron expression.
        """
        base = after or datetime.now(timezone.utc)
        # Normalise to UTC-aware
        if base.tzinfo is None:
            base = pytz.utc.localize(base)
        else:
            base = base.astimezone(pytz.utc)

        cron = croniter(expression, base)
        nxt: datetime = cron.get_next(datetime)
        # croniter returns tz-naive; interpret as UTC then strip tzinfo
        if nxt.tzinfo is None:
            nxt = pytz.utc.localize(nxt)
        return nxt.astimezone(pytz.utc).replace(tzinfo=None)

    def describe(self, expression: str) -> str:
        """
        Return a human-readable English description of the cron expression.
        Examples:
          "0 9 * * 1"     → "Every Monday at 09:00 UTC"
          "0 */6 * * *"   → "Every 6 hours"
          "*/15 * * * *"  → "Every 15 minutes"
          "0 0 1 * *"     → "On the 1st of every month at 00:00 UTC"
        """
        if not self.validate(expression):
            return f"Invalid expression: {expression!r}"

        parts = expression.strip().split()
        if len(parts) != 5:
            return expression

        minute, hour, dom, month, dow = parts

        # ── Every minute ──────────────────────────────────────────────────────
        if expression.strip() == "* * * * *":
            return "Every minute"

        # ── Every N minutes ───────────────────────────────────────────────────
        if minute.startswith("*/") and hour == "*" and dom == "*" and month == "*" and dow == "*":
            n = minute[2:]
            return f"Every {n} minutes"
        if minute == "*" and hour.startswith("*/") and dom == "*" and month == "*" and dow == "*":
            n = hour[2:]
            return f"Every {n} hours"

        # ── At a fixed time ───────────────────────────────────────────────────
        time_str = ""
        if _is_fixed(minute) and _is_fixed(hour):
            time_str = f"at {int(hour):02d}:{int(minute):02d} UTC"

        # Day-of-week
        if dow != "*" and dom == "*":
            day_str = _describe_dow(dow)
            if time_str:
                return f"{day_str} {time_str}"
            return f"{day_str}"

        # Day-of-month
        if dom != "*" and dow == "*":
            day_str = _describe_dom(dom)
            if month != "*":
                month_str = _describe_month(month)
                return f"{day_str} of {month_str} {time_str}".strip()
            if time_str:
                return f"On the {day_str} of every month {time_str}"
            return f"On the {day_str} of every month"

        # Hourly
        if _is_fixed(minute) and hour == "*":
            return f"Every hour at :{int(minute):02d}"

        # Daily
        if dom == "*" and dow == "*" and month == "*" and time_str:
            return f"Every day {time_str}"

        # Fallback: just annotate the fields
        return f"Cron: {expression}"


# ── Helpers ───────────────────────────────────────────────────────────────────


def _is_fixed(field: str) -> bool:
    """True if the field is a plain integer (no wildcards or ranges)."""
    try:
        int(field)
        return True
    except ValueError:
        return False


def _describe_dow(dow: str) -> str:
    try:
        idx = int(dow) % 7
        return f"Every {_WEEKDAY_NAMES[idx]}"
    except ValueError:
        pass
    if dow == "1-5":
        return "Every weekday (Mon–Fri)"
    if dow == "6,0" or dow == "0,6":
        return "Every weekend"
    return f"On days {dow}"


def _describe_dom(dom: str) -> str:
    try:
        n = int(dom)
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n if n < 20 else n % 10, "th")
        return f"{n}{suffix}"
    except ValueError:
        return dom


def _describe_month(month: str) -> str:
    try:
        return _MONTH_NAMES[int(month)]
    except (ValueError, IndexError):
        return month


# ── Module-level helpers (backwards compat with existing evaluator) ───────────


def validate_cron(expression: str) -> bool:
    return CronParser().validate(expression)


def compute_next_run(expression: str, timezone_str: str, after: datetime) -> datetime:
    """
    Backwards-compatible helper.
    Compute next run in the given timezone; return naive UTC datetime.
    """
    try:
        tz = pytz.timezone(timezone_str)
    except pytz.UnknownTimeZoneError:
        tz = pytz.utc

    if after.tzinfo is None:
        after_aware = pytz.utc.localize(after)
    else:
        after_aware = after.astimezone(pytz.utc)

    after_local = after_aware.astimezone(tz)
    cron = croniter(expression, after_local)
    next_local: datetime = cron.get_next(datetime)
    next_utc = next_local.astimezone(pytz.utc)
    return next_utc.replace(tzinfo=None)


# Module-level singleton
_parser: CronParser | None = None


def get_cron_parser() -> CronParser:
    global _parser
    if _parser is None:
        _parser = CronParser()
    return _parser
