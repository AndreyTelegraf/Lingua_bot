from datetime import UTC, datetime

from services.vocab_runtime.result_snapshot import compute_is_usable_as_level_prior


def test_freshness_flag_true_for_recent_attempt():
    now = datetime(2026, 3, 16, 12, 0, 0, tzinfo=UTC)
    assert compute_is_usable_as_level_prior(
        finished_at_iso="2026-03-01T12:00:00Z",
        fresh_until_days=90,
        now_utc=now,
    ) is True


def test_freshness_flag_false_for_old_attempt():
    now = datetime(2026, 3, 16, 12, 0, 0, tzinfo=UTC)
    assert compute_is_usable_as_level_prior(
        finished_at_iso="2025-10-01T12:00:00Z",
        fresh_until_days=90,
        now_utc=now,
    ) is False
