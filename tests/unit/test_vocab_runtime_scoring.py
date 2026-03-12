import json

from services.vocab_runtime.scoring import (
    ScoringInput,
    build_scoring_input_from_events,
    extract_scoring_rows_from_event_rows,
    score_attempt_v1,
)


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


def test_extract_scoring_rows_from_answer_payload() -> None:
    rows = [
        {
            "event_type": "answer_submitted",
            "payload_json": json.dumps(
                {
                    "is_correct": 1,
                    "bin_name": "1K",
                    "freq_rank": 500,
                }
            ),
        }
    ]
    out = extract_scoring_rows_from_event_rows(rows)
    assert out == [{"is_correct": 1, "bin_name": "1K", "freq_rank": 500}]


def test_extract_scoring_rows_from_nested_payload() -> None:
    rows = [
        {
            "event_type": "answer_submitted",
            "payload_json": json.dumps(
                {
                    "selected_choice": {"is_correct": 0},
                    "current_question": {"bin_name": "2K", "freq_rank": 1500},
                }
            ),
        }
    ]
    out = extract_scoring_rows_from_event_rows(rows)
    assert out == [{"is_correct": 0, "bin_name": "2K", "freq_rank": 1500}]


def test_scoring_v1_single_easy_correct_golden() -> None:
    inp = build_scoring_input_from_events(
        [{"is_correct": 1, "bin_name": "1K", "freq_rank": 500}],
        attempt_id=1,
        total_questions=1,
        correct_answers=1,
    )
    out = score_attempt_v1(inp)
    assert out["estimated_vocab_size"] == 3800
    assert out["estimated_vocab_band"] == "2.5k-4k"
    assert out["confidence"] == 0.22


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
    assert out["confidence"] == 0.2


def test_scoring_v1_two_correct_answers_easy_plus_mid_not_beginner() -> None:
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
    assert out["estimated_vocab_size"] == 5500
    assert out["estimated_vocab_band"] == "4k-6k"
    assert out["confidence"] == 0.31


def test_scoring_v1_two_correct_answers_mid_plus_hard_pushes_high() -> None:
    inp = build_scoring_input_from_events(
        [
            {"is_correct": 1, "bin_name": "2K", "freq_rank": 1100},
            {"is_correct": 1, "bin_name": "5K", "freq_rank": 2400},
        ],
        attempt_id=4,
        total_questions=2,
        correct_answers=2,
    )
    out = score_attempt_v1(inp)
    assert out["estimated_vocab_size"] == 9000
    assert out["estimated_vocab_band"] == "8k+"
    assert out["confidence"] == 0.33


def test_extract_scoring_rows_from_event_rows_still_supports_legacy_payload() -> None:
    rows = [
        {
            "event_type": "answer_submitted",
            "payload_json": json.dumps(
                {
                    "selected_choice": {"is_correct": 1},
                    "current_question": {"bin_name": "5K", "freq_rank": 2400},
                }
            ),
        }
    ]
    out = extract_scoring_rows_from_event_rows(rows)
    assert out == [{"is_correct": 1, "bin_name": "5K", "freq_rank": 2400}]
