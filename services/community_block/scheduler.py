from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(slots=True)
class SchedulerDecision:
    allowed: bool
    reason: str


def should_skip_for_cooldown(
    *,
    now: datetime,
    last_posted_at: datetime | None,
    cooldown_hours: int,
) -> SchedulerDecision:
    if last_posted_at is None:
        return SchedulerDecision(True, "no_previous_post")
    if now - last_posted_at < timedelta(hours=cooldown_hours):
        return SchedulerDecision(False, "cooldown_active")
    return SchedulerDecision(True, "cooldown_passed")


def should_skip_for_activity(
    *,
    recent_messages_count: int,
    threshold: int,
) -> SchedulerDecision:
    if recent_messages_count > threshold:
        return SchedulerDecision(False, "active_discussion")
    return SchedulerDecision(True, "activity_below_threshold")
