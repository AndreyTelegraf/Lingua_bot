from __future__ import annotations

from datetime import UTC, datetime

from services.community_block.schedule_gate import should_post_now


def test_should_post_now_within_window() -> None:
    now = datetime(2026, 3, 17, 11, 10, tzinfo=UTC)
    decision = should_post_now(now=now, daily_post_time="11:00")
    assert decision.allowed is True
    assert decision.reason == "within_daily_window"


def test_should_post_now_before_window() -> None:
    now = datetime(2026, 3, 17, 10, 59, tzinfo=UTC)
    decision = should_post_now(now=now, daily_post_time="11:00")
    assert decision.allowed is False
    assert decision.reason == "before_daily_window"


def test_should_post_now_after_window() -> None:
    now = datetime(2026, 3, 17, 12, 5, tzinfo=UTC)
    decision = should_post_now(now=now, daily_post_time="11:00")
    assert decision.allowed is False
    assert decision.reason == "after_daily_window"


def test_should_post_now_invalid_time() -> None:
    now = datetime(2026, 3, 17, 11, 10, tzinfo=UTC)
    decision = should_post_now(now=now, daily_post_time="bogus")
    assert decision.allowed is False
    assert decision.reason == "invalid_daily_post_time"
