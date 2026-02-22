from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo


ET = ZoneInfo("America/New_York")


def next_saturday_9pm_et(now_utc: datetime | None = None) -> datetime:
    now_utc = now_utc or datetime.now(timezone.utc)
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    now_et = now_utc.astimezone(ET)
    days_ahead = (5 - now_et.weekday()) % 7
    target_date = now_et.date() + timedelta(days=days_ahead)
    target_et = datetime.combine(target_date, time(hour=21, minute=0), tzinfo=ET)
    if now_et >= target_et:
        target_et += timedelta(days=7)
    return target_et.astimezone(timezone.utc)


def should_run_weekly(now_utc: datetime | None = None, grace_minutes: int = 90) -> bool:
    now_utc = now_utc or datetime.now(timezone.utc)
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    probe = now_utc - timedelta(minutes=grace_minutes)
    target = next_saturday_9pm_et(probe)
    return target <= now_utc <= target + timedelta(minutes=grace_minutes)
