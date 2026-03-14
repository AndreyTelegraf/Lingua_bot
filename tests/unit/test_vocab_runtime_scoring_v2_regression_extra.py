from services.vocab_runtime.scoring import build_scoring_input_from_events
from services.vocab_runtime.scoring_v2 import score_attempt_logistic_coverage_v2


def test_scoring_v2_regression_single_easy_correct_not_too_high() -> None:
    inp = build_scoring_input_from_events(
        [{"is_correct": 1, "bin_name": "1K", "freq_rank": 500}],
        attempt_id=201,
        total_questions=1,
        correct_answers=1,
    )
    out = score_attempt_logistic_coverage_v2(inp)
    assert out["estimated_vocab_size"] <= 4600


def test_scoring_v2_regression_mixed_easy_mid_not_overblown() -> None:
    inp = build_scoring_input_from_events(
        [
            {"is_correct": 1, "bin_name": "1K", "freq_rank": 500},
            {"is_correct": 0, "bin_name": "2K", "freq_rank": 1500},
        ],
        attempt_id=202,
        total_questions=2,
        correct_answers=1,
    )
    out = score_attempt_logistic_coverage_v2(inp)
    assert out["estimated_vocab_size"] <= 3600


def test_scoring_v2_regression_half_correct_long_sample_not_fake_high() -> None:
    inp = build_scoring_input_from_events(
        (
            [{"is_correct": 1, "bin_name": "2K", "freq_rank": 1200}] * 12
            + [{"is_correct": 0, "bin_name": "4K", "freq_rank": 2200}] * 12
        ),
        attempt_id=203,
        total_questions=24,
        correct_answers=12,
    )
    out = score_attempt_logistic_coverage_v2(inp)
    assert out["estimated_vocab_size"] <= 3400
    assert out["estimated_vocab_band"] in {"1500-2500", "2500-4000"}


def test_scoring_v2_regression_strong_long_sample_stays_high() -> None:
    inp = build_scoring_input_from_events(
        [{"is_correct": 1, "bin_name": "5K", "freq_rank": 2400}] * 24,
        attempt_id=204,
        total_questions=24,
        correct_answers=24,
    )
    out = score_attempt_logistic_coverage_v2(inp)
    assert out["estimated_vocab_size"] >= 7600
