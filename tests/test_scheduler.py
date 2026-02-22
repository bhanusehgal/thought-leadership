from __future__ import annotations

from datetime import datetime, timedelta, timezone

from agent.scheduler import ET, next_saturday_9pm_et, should_run_weekly


def test_next_saturday_is_9pm_et_summer_and_winter() -> None:
    summer_now = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
    summer_target = next_saturday_9pm_et(summer_now)
    summer_et = summer_target.astimezone(ET)
    assert summer_et.weekday() == 5
    assert summer_et.hour == 21
    assert summer_target.hour == 1  # EDT UTC-4

    winter_now = datetime(2026, 12, 1, 12, 0, tzinfo=timezone.utc)
    winter_target = next_saturday_9pm_et(winter_now)
    winter_et = winter_target.astimezone(ET)
    assert winter_et.weekday() == 5
    assert winter_et.hour == 21
    assert winter_target.hour == 2  # EST UTC-5


def test_should_run_weekly_window() -> None:
    base = next_saturday_9pm_et(datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc))
    assert should_run_weekly(base + timedelta(minutes=20), grace_minutes=90)
    assert not should_run_weekly(base + timedelta(hours=3), grace_minutes=90)
