from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ScoringInput:
    attempt_id: int
    total_questions: int
    correct_answers: int
    bin_stats: dict[str, float]
    freq_points: list[int]


def _band_midpoint(bin_name: str | None) -> int | None:
    if not bin_name:
        return None
    raw = str(bin_name).strip().upper()
    if not raw.endswith("K"):
        return None
    try:
        n = int(raw[:-1])
    except ValueError:
        return None
    low = max((n - 1) * 1000 + 1, 1)
    high = n * 1000
    return (low + high) // 2


def _estimate_size_from_signal(*, weighted_accuracy: float, avg_freq: float, max_freq: int | None, total: int) -> tuple[int, str]:
    if weighted_accuracy >= 0.95:
        size = 3800
    elif weighted_accuracy >= 0.85:
        size = 2200
    elif weighted_accuracy >= 0.72:
        size = 1400
    elif weighted_accuracy >= 0.58:
        size = 1400
    elif weighted_accuracy >= 0.45:
        size = 2200
    elif weighted_accuracy >= 0.30:
        size = 1400
    else:
        size = 700

    if total >= 2:
        if weighted_accuracy >= 0.95 and avg_freq >= 900:
            size = max(size, 5500)
        if weighted_accuracy >= 0.95 and avg_freq >= 1700:
            size = max(size, 7500)
        if weighted_accuracy >= 0.95 and (max_freq or 0) >= 2400:
            size = max(size, 9000)
        if weighted_accuracy >= 0.50 and avg_freq >= 900:
            size = max(size, 2200)

    if size >= 8000:
        band = "8k+"
    elif size >= 6000:
        band = "6k-8k"
    elif size >= 4000:
        band = "4k-6k"
    elif size >= 2500:
        band = "2.5k-4k"
    elif size >= 1500:
        band = "1.5k-2.5k"
    else:
        band = "<1.5k"

    return size, band


def score_attempt_v1(inp: ScoringInput) -> dict[str, Any]:
    total = int(inp.total_questions)
    correct = int(inp.correct_answers)

    if total <= 0:
        return {
            "scoring_model": "runtime_scoring_v1",
            "estimated_vocab_size": None,
            "estimated_vocab_band": "insufficient_data",
            "confidence": 0.0,
            "coverage_score": 0.0,
            "difficulty_score": 0.0,
            "spread_score": 0.0,
            "sample_score": 0.0,
            "weighted_bin_hits": {},
        }

    weighted_hits = dict(inp.bin_stats)
    freq_points = list(inp.freq_points)

    raw_accuracy = correct / total

    if freq_points:
        weighted_accuracy = sum(weighted_hits.values()) / max(len(freq_points), 1)
        weighted_accuracy = max(0.0, min(weighted_accuracy, 1.0))
        avg_freq = sum(freq_points) / len(freq_points)
        max_freq = max(freq_points)
        min_freq = min(freq_points)
    else:
        weighted_accuracy = raw_accuracy
        avg_freq = 0.0
        max_freq = None
        min_freq = None

    estimated_vocab_size, estimated_vocab_band = _estimate_size_from_signal(
        weighted_accuracy=weighted_accuracy,
        avg_freq=avg_freq,
        max_freq=max_freq,
        total=total,
    )

    unique_bins = len([k for k, v in weighted_hits.items() if v > 0])
    coverage_score = min(1.0, unique_bins / 4.0)

    if freq_points:
        difficulty_score = min(1.0, avg_freq / 6000.0)
        spread_score = min(1.0, ((max_freq or 0) - (min_freq or 0)) / 5000.0) if len(freq_points) >= 2 else 0.0
    else:
        difficulty_score = 0.0
        spread_score = 0.0

    sample_score = min(1.0, total / 24.0)

    confidence = (
        0.45 * sample_score
        + 0.15 * coverage_score
        + 0.15 * difficulty_score
        + 0.10 * spread_score
        + 0.15 * min(1.0, raw_accuracy)
    )
    confidence = round(max(0.15, min(confidence, 0.95)), 2)

    return {
        "scoring_model": "runtime_scoring_v1",
        "estimated_vocab_size": estimated_vocab_size,
        "estimated_vocab_band": estimated_vocab_band,
        "confidence": confidence,
        "coverage_score": round(coverage_score, 3),
        "difficulty_score": round(difficulty_score, 3),
        "spread_score": round(spread_score, 3),
        "sample_score": round(sample_score, 3),
        "weighted_bin_hits": weighted_hits,
    }


def build_scoring_input_from_events(
    rows: list[dict[str, Any]],
    *,
    attempt_id: int,
    total_questions: int,
    correct_answers: int,
) -> ScoringInput:
    weighted_hits: dict[str, float] = {}
    freq_points: list[int] = []

    for row in rows:
        is_correct = 1 if int(row.get("is_correct", 0) or 0) == 1 else 0
        bin_name = row.get("bin_name")
        freq_rank = row.get("freq_rank")

        midpoint: int | None = None
        if freq_rank is not None:
            try:
                midpoint = int(freq_rank)
            except (TypeError, ValueError):
                midpoint = None

        if midpoint is None:
            midpoint = _band_midpoint(str(bin_name) if bin_name is not None else None)

        if midpoint is None:
            midpoint = 3500

        freq_points.append(int(midpoint))

        if bin_name is not None:
            key = str(bin_name)
            if is_correct:
                weighted_hits[key] = round(weighted_hits.get(key, 0.0) + 1.0, 3)
            else:
                weighted_hits.setdefault(key, 0.0)

    return ScoringInput(
        attempt_id=int(attempt_id),
        total_questions=int(total_questions),
        correct_answers=int(correct_answers),
        bin_stats=weighted_hits,
        freq_points=freq_points,
    )


def extract_scoring_rows_from_event_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []

    for row in rows:
        event_type = str(row.get("event_type") or "")
        payload_raw = row.get("payload_json")
        reason_code = str(row.get("reason_code") or "").strip().lower()

        payload: dict[str, Any] = {}
        if payload_raw:
            try:
                payload_candidate = json.loads(payload_raw)
                if isinstance(payload_candidate, dict):
                    payload = payload_candidate
            except Exception:
                payload = {}

        candidate: dict[str, Any] = {}

        # Top-level direct fields from joined SQL rows
        for key in ("bin_name", "freq_rank", "is_correct"):
            if key in row and row.get(key) is not None:
                candidate[key] = row.get(key)

        # Legacy/current payload forms
        if "is_correct" in payload:
            candidate["is_correct"] = payload.get("is_correct")

        for key in ("bin_name", "freq_rank"):
            if key in payload and payload.get(key) is not None:
                candidate[key] = payload.get(key)

        item_obj = payload.get("item")
        if isinstance(item_obj, dict):
            candidate.setdefault("bin_name", item_obj.get("bin_name"))
            candidate.setdefault("freq_rank", item_obj.get("freq_rank"))

        current_question = payload.get("current_question")
        if isinstance(current_question, dict):
            candidate.setdefault("bin_name", current_question.get("bin_name"))
            candidate.setdefault("freq_rank", current_question.get("freq_rank"))

        selected_choice = payload.get("selected_choice")
        if isinstance(selected_choice, dict):
            if selected_choice.get("is_correct") is not None:
                candidate["is_correct"] = selected_choice.get("is_correct")

        # New production format: correctness moved into reason_code
        if candidate.get("is_correct") is None and event_type == "answer_submitted":
            if reason_code == "correct":
                candidate["is_correct"] = 1
            elif reason_code in {"wrong", "incorrect"}:
                candidate["is_correct"] = 0

        if candidate.get("is_correct") is None and event_type in {"answer_submitted", "answer", "dont_know"}:
            if payload.get("answer_kind") == "dont_know" or reason_code == "dont_know":
                candidate["is_correct"] = 0

        if candidate.get("is_correct") is None:
            continue

        out.append(candidate)

    return out


def score_attempt_default(inp: ScoringInput) -> dict[str, Any]:
    model = str(os.getenv("LINGUA_VOCAB_SCORING_MODEL", "runtime_scoring_v2") or "runtime_scoring_v2").strip().lower()

    if model in {"runtime_scoring_v2", "v2", "logistic_coverage_v2"}:
        from services.vocab_runtime.scoring_v2 import score_attempt_logistic_coverage_v2
        return score_attempt_logistic_coverage_v2(inp)

    return score_attempt_v1(inp)
