from __future__ import annotations

import sqlite3

from services.vocab_runtime.repo import get_attempt_stats
from services.vocab_runtime.service import (
    finish_active_attempt,
    get_next_question,
    start_or_resume_attempt,
    submit_answer,
    submit_choice,
)
from services.vocab_runtime.state import (
    VocabSessionState,
    clear_current_question,
    finish_session,
    set_current_question,
    start_session,
)


def begin_flow(conn: sqlite3.Connection, *, user_id: int) -> VocabSessionState:
    attempt = start_or_resume_attempt(conn, user_id=user_id)
    return start_session(user_id=user_id, attempt_id=int(attempt["attempt_id"]))


def next_step(conn: sqlite3.Connection, *, state: VocabSessionState) -> tuple[VocabSessionState, dict[str, object] | None]:
    if state.status == "finished":
        if state.attempt_id is None:
            return state, {"status": "finished", "attempt_id": None}
        return state, get_attempt_stats(conn, attempt_id=int(state.attempt_id))

    question = get_next_question(conn, user_id=state.user_id)
    if question is None:
        finished = finish_active_attempt(conn, user_id=state.user_id, completion_reason="items_exhausted")
        next_state = finish_session(state)
        return next_state, finished if finished is not None else {"status": "finished", "attempt_id": state.attempt_id}

    next_state = set_current_question(state, item_id=int(question["item_id"]))
    return next_state, question


def answer_step(
    conn: sqlite3.Connection,
    *,
    state: VocabSessionState,
    answer_text: str | None,
) -> tuple[VocabSessionState, dict[str, object]]:
    if state.attempt_id is None or state.current_item_id is None:
        raise RuntimeError("no_active_question")

    result = submit_answer(
        conn,
        user_id=state.user_id,
        attempt_id=int(state.attempt_id),
        item_id=int(state.current_item_id),
        answer_text=answer_text,
    )
    next_state = clear_current_question(state)
    return next_state, result


def answer_choice_step(
    conn: sqlite3.Connection,
    *,
    state: VocabSessionState,
    choice_id: int,
) -> tuple[VocabSessionState, dict[str, object]]:
    if state.attempt_id is None or state.current_item_id is None:
        raise RuntimeError("no_active_question")

    result = submit_choice(
        conn,
        user_id=state.user_id,
        attempt_id=int(state.attempt_id),
        item_id=int(state.current_item_id),
        choice_id=choice_id,
    )
    next_state = clear_current_question(state)
    return next_state, result

# ===== CAT layer 21: real flow branching =====

def _cat_enabled_from_kwargs(kwargs: dict) -> bool:
    raw = kwargs.get("cat_feature_enabled", kwargs.get("feature_enabled", False))
    return bool(raw)


def _branch_start_result(result):
    if not isinstance(result, dict):
        return {"mode": "legacy", "result": result}
    cat_route = result.get("cat_route")
    if cat_route is None:
        return {"mode": "legacy", "result": result}
    source = getattr(cat_route, "source", None)
    if source is None and isinstance(cat_route, dict):
        source = cat_route.get("source")
    route_result = getattr(cat_route, "route_result", None)
    if route_result is None and isinstance(cat_route, dict):
        route_result = cat_route.get("route_result")
    return {
        "mode": "cat" if source == "cat" else "legacy",
        "result": result,
        "cat_route": cat_route,
        "cat_source": source,
        "cat_route_result": route_result,
    }


def _branch_answer_result(result):
    if not isinstance(result, dict):
        return {"mode": "legacy", "result": result}
    cat_route = result.get("cat_route")
    if cat_route is None:
        return {"mode": "legacy", "result": result}
    source = getattr(cat_route, "source", None)
    if source is None and isinstance(cat_route, dict):
        source = cat_route.get("source")
    route_result = getattr(cat_route, "route_result", None)
    if route_result is None and isinstance(cat_route, dict):
        route_result = cat_route.get("route_result")
    return {
        "mode": "cat" if source == "cat" else "legacy",
        "result": result,
        "cat_route": cat_route,
        "cat_source": source,
        "cat_route_result": route_result,
    }


def start_flow(
    conn,
    *,
    user_id: int,
    cat_feature_enabled: bool = False,
    item_bank=None,
    started_at: str | None = None,
    metadata: dict | None = None,
    active_only: bool = True,
    limit: int | None = None,
):
    from services.vocab_runtime.service import start_or_resume_attempt, get_next_question

    start_result = start_or_resume_attempt(
        conn,
        user_id=int(user_id),
        cat_feature_enabled=cat_feature_enabled,
        item_bank=item_bank,
        started_at=started_at,
        metadata=metadata,
        active_only=active_only,
        limit=limit,
    )
    question_result = get_next_question(
        conn,
        user_id=int(user_id),
        cat_feature_enabled=cat_feature_enabled,
        item_bank=item_bank,
        started_at=started_at,
        metadata=metadata,
        active_only=active_only,
        limit=limit,
    )
    return {
        "attempt": _branch_start_result(start_result),
        "question": _branch_start_result(question_result),
    }


def answer_flow(
    conn,
    *,
    user_id: int,
    attempt_id: int,
    item_id: int,
    choice_id: int | None = None,
    answer_text: str | None = None,
    cat_feature_enabled: bool = False,
    item=None,
    response_value: int | float | None = None,
    is_correct: bool | None = None,
    item_bank=None,
    updated_at: str | None = None,
    metadata: dict | None = None,
):
    from services.vocab_runtime.service import submit_choice, submit_answer

    if choice_id is not None:
        result = submit_choice(
            conn,
            user_id=int(user_id),
            attempt_id=int(attempt_id),
            item_id=int(item_id),
            choice_id=int(choice_id),
            cat_feature_enabled=cat_feature_enabled,
            item=item,
            response_value=response_value,
            is_correct=is_correct,
            item_bank=item_bank,
            updated_at=updated_at,
            metadata=metadata,
        )
    else:
        result = submit_answer(
            conn,
            user_id=int(user_id),
            attempt_id=int(attempt_id),
            item_id=int(item_id),
            answer_text=answer_text,
            cat_feature_enabled=cat_feature_enabled,
            item=item,
            response_value=response_value,
            is_correct=is_correct,
            item_bank=item_bank,
            updated_at=updated_at,
            metadata=metadata,
        )
    return _branch_answer_result(result)
