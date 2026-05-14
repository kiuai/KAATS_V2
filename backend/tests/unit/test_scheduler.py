"""
Unit tests for the CronParser class and schedule-related utilities.

The module-level test_cron_parser.py covers compute_next_run() and
validate_cron() backwards-compat helpers. This file focuses on the
CronParser class API: validate(), validate_min_interval(), next_run(),
and describe().
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.scheduler.cron_parser import CronParser, get_cron_parser


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def parser() -> CronParser:
    return CronParser()


# ─────────────────────────────────────────────────────────────────────────────
# CronParser.validate()
# ─────────────────────────────────────────────────────────────────────────────

class TestCronParserValidate:
    @pytest.mark.parametrize("expr", [
        "0 9 * * 1",        # Every Monday at 9am
        "*/30 * * * *",     # Every 30 minutes
        "0 0 1 * *",        # 1st of every month
        "0 2 * * *",        # Every day at 2am
        "0 */6 * * *",      # Every 6 hours
        "15 14 1 * *",      # 1st of month at 14:15
        "0 22 * * 1-5",     # Weekdays at 22:00
        "5 4 * * 0",        # Every Sunday at 04:05
    ])
    def test_valid_expressions(self, parser: CronParser, expr: str) -> None:
        assert parser.validate(expr) is True

    @pytest.mark.parametrize("expr", [
        "not a cron",
        "99 99 99 99 99",
        "",
        "* * * *",           # Only 4 fields
        "* * * * * *",       # 6 fields (not standard 5)
        "60 * * * *",        # Minute out of range
        "* 25 * * *",        # Hour out of range
        "abc def ghi jkl mno",
    ])
    def test_invalid_expressions(self, parser: CronParser, expr: str) -> None:
        assert parser.validate(expr) is False


# ─────────────────────────────────────────────────────────────────────────────
# CronParser.validate_min_interval()
# ─────────────────────────────────────────────────────────────────────────────

class TestCronParserMinInterval:
    def test_every_15_minutes_is_allowed(self, parser: CronParser) -> None:
        assert parser.validate_min_interval("*/15 * * * *") is True

    def test_every_30_minutes_is_allowed(self, parser: CronParser) -> None:
        assert parser.validate_min_interval("*/30 * * * *") is True

    def test_hourly_is_allowed(self, parser: CronParser) -> None:
        assert parser.validate_min_interval("0 * * * *") is True

    def test_daily_is_allowed(self, parser: CronParser) -> None:
        assert parser.validate_min_interval("0 9 * * *") is True

    def test_every_5_minutes_is_rejected(self, parser: CronParser) -> None:
        assert parser.validate_min_interval("*/5 * * * *") is False

    def test_every_10_minutes_is_rejected(self, parser: CronParser) -> None:
        assert parser.validate_min_interval("*/10 * * * *") is False

    def test_every_1_minute_is_rejected(self, parser: CronParser) -> None:
        assert parser.validate_min_interval("* * * * *") is False

    def test_invalid_expression_is_rejected(self, parser: CronParser) -> None:
        assert parser.validate_min_interval("not a cron") is False


# ─────────────────────────────────────────────────────────────────────────────
# CronParser.next_run()
# ─────────────────────────────────────────────────────────────────────────────

class TestCronParserNextRun:
    def test_next_run_returns_naive_datetime(self, parser: CronParser) -> None:
        after = datetime(2026, 5, 13, 1, 0, 0)
        result = parser.next_run("0 2 * * *", after=after)
        assert result.tzinfo is None

    def test_next_run_is_in_the_future(self, parser: CronParser) -> None:
        after = datetime(2026, 5, 13, 1, 0, 0)
        result = parser.next_run("0 2 * * *", after=after)
        # next_run must be strictly after the `after` time
        assert result > after.replace(tzinfo=None)

    def test_next_run_daily_at_2am(self, parser: CronParser) -> None:
        after = datetime(2026, 5, 13, 1, 0, 0)
        result = parser.next_run("0 2 * * *", after=after)
        assert result.hour == 2
        assert result.minute == 0

    def test_next_run_weekly_monday(self, parser: CronParser) -> None:
        # 2026-05-13 is a Wednesday; next Monday is 2026-05-18
        after = datetime(2026, 5, 13, 10, 0, 0)
        result = parser.next_run("0 9 * * 1", after=after)
        assert result.weekday() == 0  # Monday

    def test_next_run_no_after_uses_now(self, parser: CronParser) -> None:
        result = parser.next_run("0 2 * * *")
        assert result.tzinfo is None
        assert isinstance(result, datetime)

    def test_next_run_aware_after_is_normalised(self, parser: CronParser) -> None:
        after = datetime(2026, 5, 13, 1, 0, 0, tzinfo=timezone.utc)
        result = parser.next_run("0 2 * * *", after=after)
        assert result.tzinfo is None
        assert result.hour == 2


# ─────────────────────────────────────────────────────────────────────────────
# CronParser.describe()
# ─────────────────────────────────────────────────────────────────────────────

class TestCronParserDescribe:
    @pytest.mark.parametrize("expr,expected", [
        ("* * * * *",   "Every minute"),
        ("*/15 * * * *", "Every 15 minutes"),
        ("*/30 * * * *", "Every 30 minutes"),
        ("* */6 * * *",  "Every 6 hours"),
        ("0 2 * * *",    "Every day at 02:00 UTC"),
        ("30 9 * * *",   "Every day at 09:30 UTC"),
        ("0 9 * * 1",    "Every Monday at 09:00 UTC"),
        ("0 9 * * 0",    "Every Sunday at 09:00 UTC"),
        ("0 0 1 * *",    "On the 1st of every month at 00:00 UTC"),
        ("0 0 15 * *",   "On the 15th of every month at 00:00 UTC"),
    ])
    def test_describe_known_patterns(
        self, parser: CronParser, expr: str, expected: str
    ) -> None:
        result = parser.describe(expr)
        assert result == expected, f"describe({expr!r}) = {result!r}, expected {expected!r}"

    def test_describe_invalid_returns_error_string(self, parser: CronParser) -> None:
        result = parser.describe("not a cron")
        assert "Invalid" in result or "not a cron" in result

    def test_describe_hourly_at_minute(self, parser: CronParser) -> None:
        result = parser.describe("30 * * * *")
        assert ":30" in result

    def test_describe_weekday_range(self, parser: CronParser) -> None:
        result = parser.describe("0 9 * * 1-5")
        assert "Mon" in result or "weekday" in result.lower() or "1-5" in result

    def test_describe_returns_non_empty_string(self, parser: CronParser) -> None:
        for expr in ["0 9 * * 1", "*/30 * * * *", "0 0 1 1 *"]:
            result = parser.describe(expr)
            assert isinstance(result, str)
            assert len(result) > 0


# ─────────────────────────────────────────────────────────────────────────────
# Singleton
# ─────────────────────────────────────────────────────────────────────────────

def test_get_cron_parser_returns_instance() -> None:
    p = get_cron_parser()
    assert isinstance(p, CronParser)


def test_get_cron_parser_is_singleton() -> None:
    p1 = get_cron_parser()
    p2 = get_cron_parser()
    assert p1 is p2
