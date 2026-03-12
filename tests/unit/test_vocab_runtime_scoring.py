from services.vocab_runtime.scoring import ScoringInput, build_scoring_input_from_events, score_attempt_v1


def test_scoring_v1_empty_input() -> None:
    out = score_attempt_v1(
        ScoringInput(
            attempt_id=1,
            total_questions=0,
            correct_answers=0,
            bin_stats={},
            freq_points=[],
        )
    )
    assert out["scoring_model"] == "runtime_scoring_v1"
    assert out["estimated_vocab_band"] == "insufficient_data"
    assert out["confidence"] == 0.0


def test_scoring_v1_single_easy_correct_golden() -> None:
    inp = build_scoring_input_from_events(
        [
            {"is_correct": 1, "bin_name": "1K", "freq_rank": 500},
        ],
        attempt_id=1,
        total_questions=1,
        correct_answers=1,
    )
    out = score_attempt_v1(inp)
    assert out["estimated_vocab_size"] == 9000
    assert out["estimated_vocab_band"] == "8k+"
    assert out["confidence"] == 0.23
    assert out["sample_score"] == 0.042
    assert out["coverage_score"] == 0.25


def test_scoring_v1_mixed_two_answers_golden() -> None:
    inp = build_scoring_input_from_events(
        [
            {"is_correct": 1, "bin_name": "1K", "freq_rank": 500},
            {"is_correct": 0, "bin_name": "2K", "freq_rank": 1500},
        ],
        attempt_id=2,
        total_questions=2,
        correct_answers=1,
    )
    out = score_attempt_v1(inp)
    assert out["estimated_vocab_size"] == 2200
    assert out["estimated_vocab_band"] == "1.5k-2.5k"
    assert out["confidence"] == 0.21
    assert out["sample_score"] == 0.083
    assert out["coverage_score"] == 0.25


def test_scoring_v1_two_correct_answers_golden() -> None:
    inp = build_scoring_input_from_events(
        [
            {"is_correct": 1, "bin_name": "1K", "freq_rank": 500},
            {"is_correct": 1, "bin_name": "2K", "freq_rank": 1500},
        ],
        attempt_id=3,
        total_questions=2,
        correct_answers=2,
    )
    out = score_attempt_v1(inp)
    assert out["estimated_vocab_size"] == 9000
    assert out["estimated_vocab_band"] == "8k+"
    assert out["confidence"] == 0.33
    assert out["coverage_score"] == 0.5
    assert out["spread_score"] == 0.2
