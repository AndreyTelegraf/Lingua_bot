from __future__ import annotations

_KNOWN_POS: list[str] = ["noun", "verb", "adjective", "adverb"]
_KNOWN_BINS: list[str] = ["1K", "2K", "5K", "10K", "20K"]


def _group_accuracy(correct: int, answered: int) -> float | None:
    return correct / answered if answered > 0 else None


def build_result(
    attempt: dict,
    answers: list[dict],
    items: list[dict],
) -> dict:
    """Pure computation: no DB access, no mutation of inputs."""
    items_by_id: dict[int, dict] = {item["id"]: item for item in items}

    # --- validate: duplicates first, orphans second ---
    seen_item_ids: set[int] = set()
    for a in answers:
        iid = a["item_id"]
        if iid in seen_item_ids:
            raise ValueError(f"duplicate answer for item_id={iid}")
        seen_item_ids.add(iid)

    for a in answers:
        iid = a["item_id"]
        if iid not in items_by_id:
            raise ValueError(f"answer item_id={iid} not found in items")

    # --- aggregate ---
    question_limit: int = attempt["question_limit"]
    answered_count: int = len(answers)
    correct_count: int = sum(1 for a in answers if a["is_correct"] == 1)
    incorrect_count: int = answered_count - correct_count

    pos_answered: dict[str, int] = {p: 0 for p in _KNOWN_POS}
    pos_correct:  dict[str, int] = {p: 0 for p in _KNOWN_POS}
    bin_answered: dict[str, int] = {b: 0 for b in _KNOWN_BINS}
    bin_correct:  dict[str, int] = {b: 0 for b in _KNOWN_BINS}

    for a in answers:
        item = items_by_id[a["item_id"]]
        pos = item["pos"]
        bn  = item["bin_name"]
        pos_answered[pos] += 1
        bin_answered[bn]  += 1
        if a["is_correct"] == 1:
            pos_correct[pos] += 1
            bin_correct[bn]  += 1

    per_pos = {
        pos: {
            "answered":  pos_answered[pos],
            "correct":   pos_correct[pos],
            "incorrect": pos_answered[pos] - pos_correct[pos],
            "accuracy":  _group_accuracy(pos_correct[pos], pos_answered[pos]),
        }
        for pos in _KNOWN_POS
    }

    per_bin = {
        bn: {
            "answered":  bin_answered[bn],
            "correct":   bin_correct[bn],
            "incorrect": bin_answered[bn] - bin_correct[bn],
            "accuracy":  _group_accuracy(bin_correct[bn], bin_answered[bn]),
        }
        for bn in _KNOWN_BINS
    }

    missing_answers = max(0, question_limit - answered_count)

    if answered_count == 0:
        signal_quality = "empty"
    elif answered_count < question_limit:
        signal_quality = "partial"
    else:
        signal_quality = "complete"

    return {
        "attempt_id":      attempt["id"],
        "question_limit":  question_limit,
        "answered_count":  answered_count,
        "correct_count":   correct_count,
        "incorrect_count": incorrect_count,
        "accuracy":        correct_count / answered_count if answered_count > 0 else 0.0,
        "per_pos":         per_pos,
        "per_bin":         per_bin,
        "coverage": {
            "expected_questions": question_limit,
            "answered_questions": answered_count,
            "complete":           answered_count == question_limit,
            "missing_answers":    missing_answers,
        },
        "signal_quality": signal_quality,
        "version":        "vocab4_result_v1",
    }
