from __future__ import annotations

import copy
import json

import pytest

from services.vocab4.result import build_result


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _attempt(question_limit: int = 3, attempt_id: int = 1) -> dict:
    return {"id": attempt_id, "question_limit": question_limit}


def _item(item_id: int, pos: str = "noun", bin_name: str = "1K") -> dict:
    return {"id": item_id, "pos": pos, "bin_name": bin_name}


def _answer(item_id: int, is_correct: int = 1) -> dict:
    return {"item_id": item_id, "is_correct": is_correct}


# ---------------------------------------------------------------------------
# test 1 — all correct
# ---------------------------------------------------------------------------

def test_all_correct() -> None:
    attempt = _attempt(question_limit=3)
    items   = [_item(1, "noun", "1K"), _item(2, "verb", "2K"), _item(3, "adjective", "5K")]
    answers = [_answer(1, 1), _answer(2, 1), _answer(3, 1)]

    result = build_result(attempt, answers, items)

    assert result["answered_count"] == 3
    assert result["correct_count"] == 3
    assert result["incorrect_count"] == 0
    assert result["accuracy"] == 1.0
    assert result["signal_quality"] == "complete"
    assert result["coverage"]["complete"] is True
    assert result["coverage"]["missing_answers"] == 0


# ---------------------------------------------------------------------------
# test 2 — all wrong
# ---------------------------------------------------------------------------

def test_all_wrong() -> None:
    attempt = _attempt(question_limit=3)
    items   = [_item(1, "noun", "1K"), _item(2, "verb", "2K"), _item(3, "adjective", "5K")]
    answers = [_answer(1, 0), _answer(2, 0), _answer(3, 0)]

    result = build_result(attempt, answers, items)

    assert result["correct_count"] == 0
    assert result["incorrect_count"] == 3
    assert result["accuracy"] == 0.0
    assert result["signal_quality"] == "complete"


# ---------------------------------------------------------------------------
# test 3 — mixed answers
# ---------------------------------------------------------------------------

def test_mixed_answers() -> None:
    attempt = _attempt(question_limit=3)
    items   = [_item(1), _item(2), _item(3)]
    answers = [_answer(1, 1), _answer(2, 1), _answer(3, 0)]

    result = build_result(attempt, answers, items)

    assert result["correct_count"] == 2
    assert result["incorrect_count"] == 1
    assert result["accuracy"] == 2 / 3
    assert result["attempt_id"] == 1
    assert result["version"] == "vocab4_result_v1"


# ---------------------------------------------------------------------------
# test 4 — per_pos aggregation
# ---------------------------------------------------------------------------

def test_per_pos_aggregation() -> None:
    attempt = _attempt(question_limit=3)
    items   = [_item(1, "noun", "1K"), _item(2, "noun", "1K"), _item(3, "verb", "2K")]
    answers = [_answer(1, 1), _answer(2, 0), _answer(3, 1)]

    result = build_result(attempt, answers, items)

    assert result["per_pos"]["noun"] == {
        "answered": 2, "correct": 1, "incorrect": 1, "accuracy": 0.5,
    }
    assert result["per_pos"]["verb"] == {
        "answered": 1, "correct": 1, "incorrect": 0, "accuracy": 1.0,
    }
    assert result["per_pos"]["adjective"] == {
        "answered": 0, "correct": 0, "incorrect": 0, "accuracy": None,
    }
    assert result["per_pos"]["adverb"] == {
        "answered": 0, "correct": 0, "incorrect": 0, "accuracy": None,
    }
    assert set(result["per_pos"].keys()) == {"noun", "verb", "adjective", "adverb"}


# ---------------------------------------------------------------------------
# test 5 — per_bin aggregation
# ---------------------------------------------------------------------------

def test_per_bin_aggregation() -> None:
    attempt = _attempt(question_limit=3)
    items   = [_item(1, "noun", "1K"), _item(2, "noun", "1K"), _item(3, "verb", "2K")]
    answers = [_answer(1, 1), _answer(2, 1), _answer(3, 0)]

    result = build_result(attempt, answers, items)

    assert result["per_bin"]["1K"] == {
        "answered": 2, "correct": 2, "incorrect": 0, "accuracy": 1.0,
    }
    assert result["per_bin"]["2K"] == {
        "answered": 1, "correct": 0, "incorrect": 1, "accuracy": 0.0,
    }
    for b in ("5K", "10K", "20K"):
        assert result["per_bin"][b] == {
            "answered": 0, "correct": 0, "incorrect": 0, "accuracy": None,
        }
    assert set(result["per_bin"].keys()) == {"1K", "2K", "5K", "10K", "20K"}


# ---------------------------------------------------------------------------
# test 6 — partial attempt signal_quality
# ---------------------------------------------------------------------------

def test_partial_attempt_signal_quality() -> None:
    attempt = _attempt(question_limit=5)
    items   = [_item(1), _item(2)]
    answers = [_answer(1, 1), _answer(2, 0)]

    result = build_result(attempt, answers, items)

    assert result["signal_quality"] == "partial"
    assert result["coverage"]["complete"] is False
    assert result["coverage"]["expected_questions"] == 5
    assert result["coverage"]["answered_questions"] == 2
    assert result["coverage"]["missing_answers"] == 3


# ---------------------------------------------------------------------------
# test 7 — empty attempt signal_quality
# ---------------------------------------------------------------------------

def test_empty_attempt_signal_quality() -> None:
    attempt = _attempt(question_limit=5)
    items   = [_item(1)]
    answers: list[dict] = []

    result = build_result(attempt, answers, items)

    assert result["signal_quality"] == "empty"
    assert result["answered_count"] == 0
    assert result["correct_count"] == 0
    assert result["incorrect_count"] == 0
    assert result["accuracy"] == 0.0
    assert result["coverage"]["complete"] is False
    assert result["coverage"]["missing_answers"] == 5
    for pos in ("noun", "verb", "adjective", "adverb"):
        assert result["per_pos"][pos]["accuracy"] is None
    for bn in ("1K", "2K", "5K", "10K", "20K"):
        assert result["per_bin"][bn]["accuracy"] is None


# ---------------------------------------------------------------------------
# test 8 — orphan answer item_id → ValueError
# ---------------------------------------------------------------------------

def test_orphan_answer_raises_value_error() -> None:
    attempt = _attempt()
    items   = [_item(1), _item(2)]
    answers = [_answer(1, 1), _answer(999, 1)]

    with pytest.raises(ValueError):
        build_result(attempt, answers, items)


# ---------------------------------------------------------------------------
# test 9 — duplicate answer item_id → ValueError
# ---------------------------------------------------------------------------

def test_duplicate_answer_raises_value_error() -> None:
    attempt = _attempt()
    items   = [_item(1), _item(2)]
    answers = [_answer(1, 1), _answer(2, 0), _answer(1, 0)]

    with pytest.raises(ValueError):
        build_result(attempt, answers, items)


# ---------------------------------------------------------------------------
# test 10 — result is JSON serializable
# ---------------------------------------------------------------------------

def test_result_is_json_serializable() -> None:
    attempt = _attempt(question_limit=1)
    items   = [_item(1, "noun", "1K")]
    answers = [_answer(1, 1)]

    result = build_result(attempt, answers, items)
    serialized = json.dumps(result)
    restored = json.loads(serialized)

    assert restored["attempt_id"] == attempt["id"]
    assert restored["version"] == "vocab4_result_v1"


# ---------------------------------------------------------------------------
# test 11 — inputs are not mutated
# ---------------------------------------------------------------------------

def test_inputs_not_mutated() -> None:
    attempt = _attempt(question_limit=3)
    items   = [_item(1, "noun", "1K"), _item(2, "verb", "2K"), _item(3, "adjective", "5K")]
    answers = [_answer(1, 1), _answer(2, 0), _answer(3, 1)]

    attempt_copy  = copy.deepcopy(attempt)
    items_copy    = copy.deepcopy(items)
    answers_copy  = copy.deepcopy(answers)

    build_result(attempt, answers, items)

    assert attempt == attempt_copy
    assert items   == items_copy
    assert answers == answers_copy
