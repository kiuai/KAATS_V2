from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.scheduler.cron_parser import compute_next_run, validate_cron


def test_validate_cron_valid():
    assert validate_cron("0 2 * * 1") is True
    assert validate_cron("*/30 * * * *") is True
    assert validate_cron("0 0 1 * *") is True


def test_validate_cron_invalid():
    assert validate_cron("not a cron") is False
    assert validate_cron("99 99 99 99 99") is False


def test_compute_next_run_utc():
    after = datetime(2026, 5, 13, 1, 0, 0)
    next_run = compute_next_run("0 2 * * *", "UTC", after)
    assert next_run.hour == 2
    assert next_run.minute == 0
    assert next_run.tzinfo is None


def test_compute_next_run_timezone():
    after = datetime(2026, 5, 13, 0, 0, 0, tzinfo=timezone.utc)
    # 9am New York = 13:00 UTC (EDT, UTC-4)
    next_run = compute_next_run("0 9 * * *", "America/New_York", after)
    assert next_run.hour == 13
    assert next_run.tzinfo is None
