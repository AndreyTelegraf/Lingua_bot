from __future__ import annotations

from dataclasses import dataclass
import inspect
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


def _answered_rows(
    *,
    item_bank: Sequence[CATItemModel],
    answers: list,
    pending_item: CATItemModel,
    pending_response_value: int | float,
) -> list[tuple[int, float, float, float | None]]:
    item_by_id = {int(item.item_id): item for item in item_bank}
    rows: list[tuple[int, float, float, float | None]] = []

    for ans in answers:
        item = item_by_id.get(int(ans.item_id))
        if item is None:
            continue
        rows.append(
            (
                int(item.item_id),
                float(ans.response_value),
                float(item.difficulty_b),
                float(item.discrimination_a),
            )
        )

    rows.append(
        (
            int(pending_item.item_id),
            float(pending_response_value),
            float(pending_item.difficulty_b),
            float(pending_item.discrimination_a),
        )
    )
    return rows


def _call_build_cat_responses(
    *,
    item_bank: Sequence[CATItemModel],
    answers: list,
    pending_item: CATItemModel,
    pending_response_value: int | float,
    pending_is_correct: bool,
):
    sig = inspect.signature(build_cat_responses)
    params = list(sig.parameters.values())
    has_var_kw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params)
    names = [
        p.name for p in params
        if p.kind in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        )
    ]

    rows = _answered_rows(
        item_bank=item_bank,
        answers=answers,
        pending_item=pending_item,
        pending_response_value=pending_response_value,
    )

    if len(names) == 1 and names[0] == "rows":
        return build_cat_responses(rows)

    canonical = {
        "rows": rows,
        "items": item_bank,
        "item_bank": item_bank,
        "candidate_items": item_bank,
        "bank": item_bank,
        "answers": answers,
        "session_answers": answers,
        "history": answers,
        "pending_item": pending_item,
        "item": pending_item,
        "pending_response_value": pending_response_value,
        "response_value": pending_response_value,
        "response": pending_response_value,
        "pending_is_correct": pending_is_correct,
        "is_correct": pending_is_correct,
    }

    if has_var_kw:
        return build_cat_responses(
            items=item_bank,
            answers=answers,
            pending_item=pending_item,
            pending_response_value=pending_response_value,
            pending_is_correct=pending_is_correct,
        )

    kwargs = {name: canonical[name] for name in names if name in canonical}
    if names and len(kwargs) == len(names):
        return build_cat_responses(**kwargs)

    last_exc: Exception | None = None
    for args in [
        (rows,),
        (item_bank, answers, pending_item, pending_response_value, pending_is_correct),
        (item_bank, answers),
    ]:
        try:
            return build_cat_responses(*args)
        except TypeError as exc:
            last_exc = exc

    if last_exc is not None:
        raise last_exc
    raise TypeError("could not adapt build_cat_responses signature")


def _call_estimate_from_items(
    *,
    item_bank: Sequence[CATItemModel],
    responses,
) -> CATEstimate:
    sig = inspect.signature(estimate_from_items)
    params = list(sig.parameters.values())
    has_var_kw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params)
    names = [
        p.name for p in params
        if p.kind in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        )
    ]

    if has_var_kw:
        return estimate_from_items(items=item_bank, responses=responses)

    if "correctness" in names:
        item_by_id = {int(item.item_id): item for item in item_bank}
        answered_items: list[CATItemModel] = []
        correctness: list[float] = []
        for r in responses:
            item_id = int(getattr(r, "item_id"))
            item = item_by_id.get(item_id)
            if item is None:
                continue
            answered_items.append(item)
            correctness.append(float(getattr(r, "score")))
        return estimate_from_items(answered_items, correctness=correctness)

    canonical = {
        "items": item_bank,
        "item_bank": item_bank,
        "candidate_items": item_bank,
        "bank": item_bank,
        "responses": responses,
        "answer_rows": responses,
    }

    kwargs = {name: canonical[name] for name in names if name in canonical}
    if names and len(kwargs) == len(names):
        return estimate_from_items(**kwargs)

    last_exc: Exception | None = None
    for args in [
        (item_bank, responses),
        (responses, item_bank),
    ]:
        try:
            return estimate_from_items(*args)
        except TypeError as exc:
            last_exc = exc

    if last_exc is not None:
        raise last_exc
    raise TypeError("could not adapt estimate_from_items signature")


def plan_next_cat_step(
    session: CATSessionState,
    *,
    candidate_items: Sequence[CATItemModel],
) -> CATOrchestrationStep:
    if not _active_status(session):
        raise ValueError("session must be active")

    estimate = _estimate_from_session(session)

    stop = should_stop_cat(
        questions_answered=len(session.answers),
        current_se=estimate.se,
    )
    if bool(stop.should_stop):
        finish_cat_session(
            session,
            final_estimate=estimate,
            reason=stop.reason,
        )
        return CATOrchestrationStep(
            action="stop",
            estimate=estimate,
            next_item=None,
            stop_reason=stop.reason,
        )

    administered = {int(x) for x in session.items_administered}
    pool = [item for item in candidate_items if int(item.item_id) not in administered]

    if not pool:
        finish_cat_session(
            session,
            final_estimate=estimate,
            reason="item_bank_exhausted",
        )
        return CATOrchestrationStep(
            action="stop",
            estimate=estimate,
            next_item=None,
            stop_reason="item_bank_exhausted",
        )

    next_item = select_next_item_for_theta(
        items=pool,
        theta=estimate.theta,
        exclude_item_ids=None,
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

    responses = _call_build_cat_responses(
        item_bank=item_bank,
        answers=provisional_answers,
        pending_item=item,
        pending_response_value=response_value,
        pending_is_correct=is_correct,
    )
    new_estimate = _call_estimate_from_items(
        item_bank=item_bank,
        responses=responses,
    )

    append_answer(
        session,
        item=item,
        response_value=int(response_value),
        is_correct=bool(is_correct),
        estimate_after=new_estimate,
        updated_at=updated_at,
    )

    return plan_next_cat_step(
        session,
        candidate_items=item_bank,
    )
