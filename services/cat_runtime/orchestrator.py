from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .estimator import CATEstimate, build_cat_responses, estimate_from_items
from .item_model import CATItemModel
from .selector import select_next_item_for_theta
from .session import CATSessionState, append_answer, finish_cat_session
from .stopping import should_stop_cat


@dataclass(slots=True)
class CATOrchestrationStep:
    action: str
    estimate: CATEstimate | None
    next_item: CATItemModel | None
    stop_reason: str | None = None


def _estimate_from_session(session: CATSessionState) -> CATEstimate:
    theta = float(session.theta if session.theta is not None else 0.0)
    se = float(session.se if session.se is not None else 99.0)
    information = 0.0 if se <= 0 else 1.0 / (se * se)
    return CATEstimate(
        theta=theta,
        se=se,
        information=information,
        items_answered=len(session.answers),
        converged=False,
    )


def _active_status(session: CATSessionState) -> bool:
    return str(session.status or "").strip().lower() in {"in_progress", "active"}


def plan_next_cat_step(
    session: CATSessionState,
    *,
    candidate_items: Sequence[CATItemModel],
) -> CATOrchestrationStep:
    if not _active_status(session):
        raise ValueError("session must be active")

    estimate = _estimate_from_session(session)

    stop = should_stop_cat(
        estimate=estimate,
        items_answered=len(session.answers),
    )
    if bool(stop.should_stop):
        finish_cat_session(
            session,
            final_estimate=estimate,
            stop_reason=str(stop.reason),
        )
        return CATOrchestrationStep(
            action="stop",
            estimate=estimate,
            next_item=None,
            stop_reason=str(stop.reason),
        )

    administered = {int(x) for x in session.items_administered}
    pool = [item for item in candidate_items if int(item.item_id) not in administered]

    if not pool:
        finish_cat_session(
            session,
            final_estimate=estimate,
            stop_reason="item_bank_exhausted",
        )
        return CATOrchestrationStep(
            action="stop",
            estimate=estimate,
            next_item=None,
            stop_reason="item_bank_exhausted",
        )

    next_item = select_next_item_for_theta(
        candidate_items=pool,
        estimate=estimate,
    )

    return CATOrchestrationStep(
        action="ask",
        estimate=estimate,
        next_item=next_item,
        stop_reason=None,
    )


def record_answer_and_plan_next(
    session: CATSessionState,
    *,
    item: CATItemModel,
    response_value: int | float,
    is_correct: bool,
    item_bank: Sequence[CATItemModel],
    updated_at: str | None = None,
) -> CATOrchestrationStep:
    provisional_answers = list(session.answers)
    responses = build_cat_responses(
        items=item_bank,
        answers=provisional_answers,
        pending_item=item,
        pending_response_value=response_value,
        pending_is_correct=is_correct,
    )
    new_estimate = estimate_from_items(
        items=item_bank,
        responses=responses,
    )

    append_answer(
        session,
        item=item,
        response_value=response_value,
        is_correct=is_correct,
        estimate_after=new_estimate,
        updated_at=updated_at,
    )

    return plan_next_cat_step(
        session,
        candidate_items=item_bank,
    )
