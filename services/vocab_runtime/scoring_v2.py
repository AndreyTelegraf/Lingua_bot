from __future__ import annotations

import math
from typing import Any

from services.vocab_runtime.scoring import ScoringInput


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def _safe_mean(values: list[int]) -> float:
    return (sum(values) / len(values)) if values else 0.0


def _safe_unique_positive_bins(weighted_hits: dict[str, float]) -> int:
    return len([k for k, v in weighted_hits.items() if float(v) > 0.0])


def _band_from_size(size: int | None) -> str:
    if size is None:
        return "insufficient_data"
    if size >= 8000:
        return "8k+"
    if size >= 6000:
        return "6k-8k"
    if size >= 4000:
        return "4k-6k"
    if size >= 2500:
        return "2.5k-4k"
    if size >= 1500:
        return "1.5k-2.5k"
    return "<1.5k"


def _estimate_vocab_size_v2(
    *,
    total: int,
    correct: int,
    weighted_accuracy: float,
    avg_freq: float,
    max_freq: int | None,
    coverage_score: float,
    sample_score: float,
    spread_score: float,
) -> int:
    freq_signal = _clamp(avg_freq / 2600.0, 0.0, 1.0)
    hard_peak_signal = _clamp((max_freq or 0) / 3200.0, 0.0, 1.0)

    gated_freq = freq_signal * weighted_accuracy
    gated_peak = hard_peak_signal * weighted_accuracy
    sample_support = sample_score * max(0.0, weighted_accuracy - 0.45)

    wrong_answers = max(total - correct, 0)
    wrong_ratio = _clamp(wrong_answers / total, 0.0, 1.0) if total > 0 else 0.0

    mixed_penalty = (
        1.10 * wrong_ratio
        + 0.55 * spread_score * wrong_ratio
        + 0.15 * coverage_score * wrong_ratio
    )

    evidence = (
        3.05 * weighted_accuracy
        + 0.28 * gated_freq
        + 0.12 * gated_peak
        + 0.10 * coverage_score
        + 0.10 * sample_support
        - mixed_penalty
        - 2.18
    )

    latent = _sigmoid(evidence)
    base_size = 700 + int(round(latent * 8400))

    if weighted_accuracy <= 0.05:
        base_size = min(base_size, 1200)
    elif weighted_accuracy <= 0.25:
        base_size = min(base_size, 2200)
    elif weighted_accuracy <= 0.50:
        base_size = min(base_size, 3200)
    elif weighted_accuracy <= 0.60:
        base_size = min(base_size, 4300)

    if sample_score >= 0.80 and weighted_accuracy <= 0.55:
        base_size = min(base_size, 3000)
    elif sample_score >= 0.80 and weighted_accuracy <= 0.65 and wrong_ratio >= 0.20:
        base_size = min(base_size, 4200)

    tiny_hard_perfect = (
        total <= 2
        and correct == total
        and weighted_accuracy >= 0.95
        and avg_freq >= 1400
    )

    if sample_score < 0.10:
        cap = 4380 + int(round(700 * gated_freq + 520 * gated_peak))
        cap = min(cap, 5900)

        if gated_freq <= 0.22 and gated_peak <= 0.20:
            cap = min(cap, 4500)

        # Hotfix: allow genuine tiny hard-perfect cases above the generic tiny cap.
        if tiny_hard_perfect:
            cap = max(cap, 6100)

    elif sample_score < 0.20:
        cap = 5900 + int(round(520 * gated_freq + 420 * gated_peak))
        cap = min(cap, 7600)
    elif sample_score < 0.35:
        cap = 7800 + int(round(240 * gated_freq + 180 * gated_peak))
        cap = min(cap, 8600)
    else:
        cap = 10000

    if tiny_hard_perfect:
        rescue_floor = 5600 + int(round(450 * gated_freq + 220 * gated_peak))
        base_size = max(base_size, min(rescue_floor, 6900))

    if sample_score >= 0.95 and weighted_accuracy >= 0.90:
        strong_floor = 7600 + int(round(620 * gated_freq + 240 * gated_peak))
        base_size = max(base_size, min(strong_floor, 9000))

    return max(700, min(base_size, cap))


def score_attempt_logistic_coverage_v2(inp: ScoringInput) -> dict[str, Any]:
    total = int(inp.total_questions)
    correct = int(inp.correct_answers)

    if total <= 0:
        return {
            "scoring_model": "runtime_scoring_v2",
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

    raw_accuracy = _clamp(correct / total, 0.0, 1.0)

    if freq_points:
        weighted_accuracy = _clamp(sum(weighted_hits.values()) / max(len(freq_points), 1), 0.0, 1.0)
        avg_freq = _safe_mean(freq_points)
        max_freq = max(freq_points)
        min_freq = min(freq_points)
        difficulty_score = _clamp(avg_freq / 3200.0, 0.0, 1.0)
        spread_score = _clamp(((max_freq or 0) - (min_freq or 0)) / 4000.0, 0.0, 1.0) if len(freq_points) >= 2 else 0.0
    else:
        weighted_accuracy = raw_accuracy
        avg_freq = 0.0
        max_freq = None
        min_freq = None
        difficulty_score = 0.0
        spread_score = 0.0

    unique_positive_bins = _safe_unique_positive_bins(weighted_hits)
    coverage_score = _clamp(unique_positive_bins / 4.0, 0.0, 1.0)
    sample_score = _clamp(total / 24.0, 0.0, 1.0)

    estimated_vocab_size = _estimate_vocab_size_v2(
        total=total,
        correct=correct,
        weighted_accuracy=weighted_accuracy,
        avg_freq=avg_freq,
        max_freq=max_freq,
        coverage_score=coverage_score,
        sample_score=sample_score,
        spread_score=spread_score,
    )
    estimated_vocab_band = _band_from_size(estimated_vocab_size)

    confidence = (
        0.42 * sample_score
        + 0.18 * coverage_score
        + 0.12 * difficulty_score
        + 0.08 * spread_score
        + 0.20 * weighted_accuracy
    )
    confidence = round(_clamp(confidence, 0.15, 0.95), 2)

    return {
        "scoring_model": "runtime_scoring_v2",
        "estimated_vocab_size": estimated_vocab_size,
        "estimated_vocab_band": estimated_vocab_band,
        "confidence": confidence,
        "coverage_score": round(coverage_score, 3),
        "difficulty_score": round(difficulty_score, 3),
        "spread_score": round(spread_score, 3),
        "sample_score": round(sample_score, 3),
        "weighted_bin_hits": weighted_hits,
    }
