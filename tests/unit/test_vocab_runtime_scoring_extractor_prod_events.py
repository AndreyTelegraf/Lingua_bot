import json

from services.vocab_runtime.scoring import extract_scoring_rows_from_event_rows


def test_extract_scoring_rows_from_prod_answer_submitted_reason_code_correct() -> None:
    rows = [
        {
            "event_type": "answer_submitted",
            "reason_code": "correct",
            "payload_json": json.dumps(
                {
                    "selected_choice_id": 363,
                    "selected_choice_text": "вода",
                }
            ),
            "bin_name": "2K",
            "freq_rank": 1200,
        }
    ]
    out = extract_scoring_rows_from_event_rows(rows)
    assert out == [{"is_correct": 1, "bin_name": "2K", "freq_rank": 1200}]


def test_extract_scoring_rows_from_prod_answer_submitted_reason_code_wrong() -> None:
    rows = [
        {
            "event_type": "answer_submitted",
            "reason_code": "wrong",
            "payload_json": json.dumps(
                {
                    "selected_choice_id": 999,
                    "selected_choice_text": "что-то не то",
                }
            ),
            "bin_name": "5K",
            "freq_rank": 2400,
        }
    ]
    out = extract_scoring_rows_from_event_rows(rows)
    assert out == [{"is_correct": 0, "bin_name": "5K", "freq_rank": 2400}]


def test_extract_scoring_rows_ignores_non_answer_events_even_if_payload_exists() -> None:
    rows = [
        {
            "event_type": "question_shown",
            "reason_code": None,
            "payload_json": json.dumps({"callback_token": "v3007:1:76"}),
            "bin_name": "2K",
            "freq_rank": 1200,
        }
    ]
    out = extract_scoring_rows_from_event_rows(rows)
    assert out == []


def test_extract_scoring_rows_prod_mix_two_correct_answers() -> None:
    rows = [
        {
            "event_type": "answer_submitted",
            "reason_code": "correct",
            "payload_json": json.dumps({"selected_choice_id": 363, "selected_choice_text": "вода"}),
            "bin_name": "2K",
            "freq_rank": 1200,
        },
        {
            "event_type": "answer_submitted",
            "reason_code": "correct",
            "payload_json": json.dumps({"selected_choice_id": 371, "selected_choice_text": "открывать"}),
            "bin_name": "5K",
            "freq_rank": 2400,
        },
    ]
    out = extract_scoring_rows_from_event_rows(rows)
    assert out == [
        {"is_correct": 1, "bin_name": "2K", "freq_rank": 1200},
        {"is_correct": 1, "bin_name": "5K", "freq_rank": 2400},
    ]
