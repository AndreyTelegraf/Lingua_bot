from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class TimeGateDecision:
    allowed: bool
    reason: str


def should_post_now(*, now: datetime, daily_post_time: str, tolerance_minutes: int = 59) -> TimeGateDecision:
    try:
        hour_s, minute_s = daily_post_time.split(":", 1)
        target_hour = int(hour_s)
        target_minute = int(minute_s)
    except Exception:
        return TimeGateDecision(False, "invalid_daily_post_time")

    current_minutes = now.hour * 60 + now.minute
    target_minutes = target_hour * 60 + target_minute

    if current_minutes < target_minutes:
        return TimeGateDecision(False, "before_daily_window")

    if current_minutes > target_minutes + tolerance_minutes:
        return TimeGateDecision(False, "after_daily_window")

    return TimeGateDecision(True, "within_daily_window")
