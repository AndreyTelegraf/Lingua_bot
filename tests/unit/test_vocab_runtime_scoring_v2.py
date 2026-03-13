from services.vocab_runtime.scoring import ScoringInput, build_scoring_input_from_events
from services.vocab_runtime.scoring_v2 import score_attempt_logistic_coverage_v2


EXPECTED_KEYS = {
    "scoring_model",
    "estimated_vocab_size",
    "estimated_vocab_band",
    "confidence",
    "coverage_score",
    "difficulty_score",
    "spread_score",
    "sample_score",
    "weighted_bin_hits",
}


def test_scoring_v2_empty_input_contract() -> None:
    out = score_attempt_logistic_coverage_v2(
        ScoringInput(
            attempt_id=1,
            total_questions=0,
            correct_answers=0,
            bin_stats={},
            freq_points=[],
        )
    )
    assert set(out.keys()) == EXPECTED_KEYS
    assert out["scoring_model"] == "runtime_scoring_v2"
    assert out["estimated_vocab_size"] is None
    assert out["estimated_vocab_band"] == "insufficient_data"
    assert out["confidence"] == 0.0
    assert out["weighted_bin_hits"] == {}


def test_scoring_v2_preserves_contract_types_on_non_empty_input() -> None:
    inp = build_scoring_input_from_events(
        [{"is_correct": 1, "bin_name": "1K", "freq_rank": 500}],
        attempt_id=1,
        total_questions=1,
        correct_answers=1,
    )
    out = score_attempt_logistic_coverage_v2(inp)

    assert set(out.keys()) == EXPECTED_KEYS
    assert out["scoring_model"] == "runtime_scoring_v2"
    assert isinstance(out["estimated_vocab_size"], int)
    assert isinstance(out["estimated_vocab_band"], str)
    assert isinstance(out["confidence"], float)
    assert isinstance(out["coverage_score"], float)
    assert isinstance(out["difficulty_score"], float)
    assert isinstance(out["spread_score"], float)
    assert isinstance(out["sample_score"], float)
    assert isinstance(out["weighted_bin_hits"], dict)


def test_scoring_v2_stronger_profile_scores_higher_than_weaker_profile() -> None:
    weak = build_scoring_input_from_events(
        [
            {"is_correct": 1, "bin_name": "1K", "freq_rank": 500},
            {"is_correct": 0, "bin_name": "2K", "freq_rank": 1500},
        ],
        attempt_id=2,
        total_questions=2,
        correct_answers=1,
    )
    strong = build_scoring_input_from_events(
        [
            {"is_correct": 1, "bin_name": "2K", "freq_rank": 1100},
            {"is_correct": 1, "bin_name": "5K", "freq_rank": 2400},
        ],
        attempt_id=3,
        total_questions=2,
        correct_answers=2,
    )

    weak_out = score_attempt_logistic_coverage_v2(weak)
    strong_out = score_attempt_logistic_coverage_v2(strong)

    assert strong_out["estimated_vocab_size"] > weak_out["estimated_vocab_size"]
    assert strong_out["confidence"] >= weak_out["confidence"]


def test_scoring_v2_larger_sample_increases_confidence_for_same_signal() -> None:
    small = build_scoring_input_from_events(
        [{"is_correct": 1, "bin_name": "5K", "freq_rank": 2400}] * 2,
        attempt_id=4,
        total_questions=2,
        correct_answers=2,
    )
    large = build_scoring_input_from_events(
        [{"is_correct": 1, "bin_name": "5K", "freq_rank": 2400}] * 24,
        attempt_id=5,
        total_questions=24,
        correct_answers=24,
    )

    small_out = score_attempt_logistic_coverage_v2(small)
    large_out = score_attempt_logistic_coverage_v2(large)

    assert large_out["confidence"] > small_out["confidence"]
    assert large_out["estimated_vocab_size"] >= small_out["estimated_vocab_size"]


def test_scoring_v2_tiny_hard_sample_does_not_jump_straight_to_absurd_ceiling() -> None:
    tiny_hard = build_scoring_input_from_events(
        [
            {"is_correct": 1, "bin_name": "2K", "freq_rank": 1100},
            {"is_correct": 1, "bin_name": "5K", "freq_rank": 2400},
        ],
        attempt_id=6,
        total_questions=2,
        correct_answers=2,
    )
    out = score_attempt_logistic_coverage_v2(tiny_hard)

    assert out["estimated_vocab_size"] < 9000
    assert out["confidence"] < 0.5


def test_scoring_v2_weighted_bin_hits_passthrough() -> None:
    inp = build_scoring_input_from_events(
        [
            {"is_correct": 1, "bin_name": "1K", "freq_rank": 300},
            {"is_correct": 1, "bin_name": "2K", "freq_rank": 1200},
            {"is_correct": 0, "bin_name": "4K", "freq_rank": 2200},
            {"is_correct": 0, "bin_name": "6K", "freq_rank": 3300},
        ],
        attempt_id=7,
        total_questions=4,
        correct_answers=2,
    )
    out = score_attempt_logistic_coverage_v2(inp)

    assert out["weighted_bin_hits"] == {
        "1K": 1.0,
        "2K": 1.0,
        "4K": 0.0,
        "6K": 0.0,
    }
