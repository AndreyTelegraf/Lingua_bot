from services.vocab_runtime.scoring import build_scoring_input_from_events
from services.vocab_runtime.scoring_v2 import score_attempt_logistic_coverage_v2


def test_scoring_v2_regression_weak_24_wrong_stays_low() -> None:
    inp = build_scoring_input_from_events(
        [{"is_correct": 0, "bin_name": "1K", "freq_rank": 500}] * 24,
        attempt_id=100,
        total_questions=24,
        correct_answers=0,
    )
    out = score_attempt_logistic_coverage_v2(inp)
    assert out["estimated_vocab_size"] <= 1500
    assert out["estimated_vocab_band"] == "<500"


def test_scoring_v2_regression_half_correct_24_is_not_fake_high() -> None:
    inp = build_scoring_input_from_events(
        (
            [{"is_correct": 1, "bin_name": "2K", "freq_rank": 1200}] * 12
            + [{"is_correct": 0, "bin_name": "4K", "freq_rank": 2200}] * 12
        ),
        attempt_id=101,
        total_questions=24,
        correct_answers=12,
    )
    out = score_attempt_logistic_coverage_v2(inp)
    assert out["estimated_vocab_size"] <= 4200


def test_scoring_v2_regression_tiny_easy_perfect_not_insane() -> None:
    inp = build_scoring_input_from_events(
        [{"is_correct": 1, "bin_name": "1K", "freq_rank": 500}],
        attempt_id=102,
        total_questions=1,
        correct_answers=1,
    )
    out = score_attempt_logistic_coverage_v2(inp)
    assert out["estimated_vocab_size"] <= 5200


def test_scoring_v2_regression_tiny_hard_perfect_beats_tiny_easy_perfect() -> None:
    easy = build_scoring_input_from_events(
        [{"is_correct": 1, "bin_name": "1K", "freq_rank": 500}],
        attempt_id=103,
        total_questions=1,
        correct_answers=1,
    )
    hard = build_scoring_input_from_events(
        [
            {"is_correct": 1, "bin_name": "2K", "freq_rank": 1100},
            {"is_correct": 1, "bin_name": "5K", "freq_rank": 2400},
        ],
        attempt_id=104,
        total_questions=2,
        correct_answers=2,
    )
    easy_out = score_attempt_logistic_coverage_v2(easy)
    hard_out = score_attempt_logistic_coverage_v2(hard)
    assert hard_out["estimated_vocab_size"] > easy_out["estimated_vocab_size"]
