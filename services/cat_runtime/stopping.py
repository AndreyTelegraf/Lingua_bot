from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class CATStoppingDecision:
    should_stop: bool
    reason: str | None
    questions_answered: int
    min_questions: int
    max_questions: int
    current_se: float | None
    target_se: float | None


def should_stop_cat(
    *,
    questions_answered: int,
    current_se: float | None,
    min_questions: int = 8,
    max_questions: int = 24,
    target_se: float = 0.35,
) -> CATStoppingDecision:
    qa = int(questions_answered)
    min_q = int(min_questions)
    max_q = int(max_questions)
    target = float(target_se)

    if min_q < 1:
        raise ValueError("min_questions must be >= 1")
    if max_q < min_q:
        raise ValueError("max_questions must be >= min_questions")
    if target <= 0:
        raise ValueError("target_se must be > 0")

    se_value = None if current_se is None else float(current_se)

    if qa >= max_q:
        return CATStoppingDecision(
            should_stop=True,
            reason="max_questions_reached",
            questions_answered=qa,
            min_questions=min_q,
            max_questions=max_q,
            current_se=se_value,
            target_se=target,
        )

    if qa < min_q:
        return CATStoppingDecision(
            should_stop=False,
            reason=None,
            questions_answered=qa,
            min_questions=min_q,
            max_questions=max_q,
            current_se=se_value,
            target_se=target,
        )

    if se_value is not None and se_value <= target:
        return CATStoppingDecision(
            should_stop=True,
            reason="target_precision_reached",
            questions_answered=qa,
            min_questions=min_q,
            max_questions=max_q,
            current_se=se_value,
            target_se=target,
        )

    return CATStoppingDecision(
        should_stop=False,
        reason=None,
        questions_answered=qa,
        min_questions=min_q,
        max_questions=max_q,
        current_se=se_value,
        target_se=target,
    )
