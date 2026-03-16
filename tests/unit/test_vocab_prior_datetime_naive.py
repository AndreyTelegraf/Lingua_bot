from datetime import UTC, datetime

from services.vocab_runtime.result_snapshot import compute_is_usable_as_level_prior


def test_compute_is_usable_as_level_prior_accepts_naive_iso():
    now = datetime(2026, 3, 16, 15, 0, 0, tzinfo=UTC)
    assert compute_is_usable_as_level_prior(
        finished_at_iso="2026-03-16 14:16:23",
        fresh_until_days=90,
        now_utc=now,
    ) is True
