from services.vocab_runtime.scoring import build_scoring_input_from_events
from services.vocab_runtime.scoring_v2 import score_attempt_logistic_coverage_v2


def test_scoring_v2f_tiny_easy_perfect_not_over_45k() -> None:
    inp = build_scoring_input_from_events(
        [{"is_correct": 1, "bin_name": "1K", "freq_rank": 500}],
        attempt_id=301,
        total_questions=1,
        correct_answers=1,
    )
    out = score_attempt_logistic_coverage_v2(inp)
    assert out["estimated_vocab_size"] <= 4500


def test_scoring_v2f_tiny_mixed_not_over_32k() -> None:
    inp = build_scoring_input_from_events(
        [
            {"is_correct": 1, "bin_name": "1K", "freq_rank": 500},
            {"is_correct": 0, "bin_name": "2K", "freq_rank": 1500},
        ],
        attempt_id=302,
        total_questions=2,
        correct_answers=1,
    )
    out = score_attempt_logistic_coverage_v2(inp)
    assert out["estimated_vocab_size"] <= 3200


def test_scoring_v2f_medium_mixed_not_two_bands_above_baseline() -> None:
    inp = build_scoring_input_from_events(
        [
            {"is_correct": 1, "bin_name": "1K", "freq_rank": 300},
            {"is_correct": 1, "bin_name": "1K", "freq_rank": 380},
            {"is_correct": 1, "bin_name": "1K", "freq_rank": 500},
            {"is_correct": 1, "bin_name": "2K", "freq_rank": 1100},
            {"is_correct": 1, "bin_name": "2K", "freq_rank": 1200},
            {"is_correct": 0, "bin_name": "4K", "freq_rank": 2400},
            {"is_correct": 0, "bin_name": "4K", "freq_rank": 2600},
            {"is_correct": 0, "bin_name": "6K", "freq_rank": 3200},
        ],
        attempt_id=303,
        total_questions=8,
        correct_answers=5,
    )
    out = score_attempt_logistic_coverage_v2(inp)
    assert out["estimated_vocab_size"] <= 4300


def test_scoring_v2f_long_mid_half_not_over_3k() -> None:
    inp = build_scoring_input_from_events(
        [{"is_correct": 1, "bin_name": "2K", "freq_rank": 1200}] * 12
        + [{"is_correct": 0, "bin_name": "4K", "freq_rank": 2200}] * 12,
        attempt_id=304,
        total_questions=24,
        correct_answers=12,
    )
    out = score_attempt_logistic_coverage_v2(inp)
    assert out["estimated_vocab_size"] <= 3000
    assert out["estimated_vocab_band"] in {"1.5k-2.5k", "2.5k-4k"}


def test_scoring_v2f_tiny_mid_hard_perfect_rescued_above_easy() -> None:
    easy = build_scoring_input_from_events(
        [{"is_correct": 1, "bin_name": "1K", "freq_rank": 500}],
        attempt_id=305,
        total_questions=1,
        correct_answers=1,
    )
    hard = build_scoring_input_from_events(
        [
            {"is_correct": 1, "bin_name": "2K", "freq_rank": 1100},
            {"is_correct": 1, "bin_name": "5K", "freq_rank": 2400},
        ],
        attempt_id=306,
        total_questions=2,
        correct_answers=2,
    )
    easy_out = score_attempt_logistic_coverage_v2(easy)
    hard_out = score_attempt_logistic_coverage_v2(hard)
    assert hard_out["estimated_vocab_size"] > easy_out["estimated_vocab_size"]
    assert hard_out["estimated_vocab_size"] >= 5600


def test_scoring_v2f_long_strong_hard_stays_high() -> None:
    inp = build_scoring_input_from_events(
        [{"is_correct": 1, "bin_name": "5K", "freq_rank": 2400}] * 24,
        attempt_id=307,
        total_questions=24,
        correct_answers=24,
    )
    out = score_attempt_logistic_coverage_v2(inp)
    assert out["estimated_vocab_size"] >= 7600
    assert out["estimated_vocab_band"] == "8k+"
