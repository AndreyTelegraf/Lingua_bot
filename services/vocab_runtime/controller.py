from __future__ import annotations

import sqlite3

from services.vocab_runtime.repo import get_attempt_stats
from services.vocab_runtime.flow import answer_choice_step, begin_flow, next_step, finish_active_attempt
from services.vocab_runtime.renderer import build_question_payload
from services.vocab_runtime.service import start_or_resume_attempt, get_next_question, submit_choice
from services.vocab_runtime.state import (
    VocabSessionState,
    clear_current_question,
    finish_session,
    set_current_question,
    start_session,
)


def start_controller(conn: sqlite3.Connection, *, user_id: int) -> VocabSessionState:
    return begin_flow(conn, user_id=user_id)


def get_next_payload(
    conn: sqlite3.Connection,
    *,
    state: VocabSessionState,
) -> tuple[VocabSessionState, dict[str, object] | None]:
    next_state, data = next_step(conn, state=state)
    if data is None:
        return next_state, None

    if next_state.current_item_id is None:
        return next_state, data

    payload = build_question_payload(
        conn,
        item_id=int(next_state.current_item_id),
        attempt_id=int(next_state.attempt_id),
    )
    return next_state, payload


def submit_choice_and_continue(
    conn: sqlite3.Connection,
    *,
    state: VocabSessionState,
    choice_id: int,
) -> tuple[VocabSessionState, dict[str, object]]:
    return answer_choice_step(conn, state=state, choice_id=choice_id)


def _merge_cat_question_fields(
    *,
    legacy_payload: dict[str, object],
    raw_question: dict[str, object],
) -> dict[str, object]:
    out = dict(legacy_payload)

    for key in (
        "cat_route",
        "runtime_branch",
        "runtime_native_payload",
        "cat_native",
        "visible_mode",
        "visible_semantics",
        "cat_payload_kind",
    ):
        if key in raw_question:
            out[key] = raw_question[key]

    return out


def start_controller_toggle(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    cat_live_enabled: bool = False,
) -> VocabSessionState:
    if not cat_live_enabled:
        return start_controller(conn, user_id=user_id)

    attempt = start_or_resume_attempt(
        conn,
        user_id=user_id,
        cat_feature_enabled=True,
    )
    attempt_id = int(attempt["attempt_id"])
    return start_session(user_id=user_id, attempt_id=attempt_id)


def get_next_payload_toggle(
    conn: sqlite3.Connection,
    *,
    state: VocabSessionState,
    cat_live_enabled: bool = False,
) -> tuple[VocabSessionState, dict[str, object] | None]:
    if not cat_live_enabled:
        return get_next_payload(conn, state=state)

    if state.status == "finished":
        if state.attempt_id is None:
            return state, {"status": "finished", "attempt_id": None}
        return state, get_attempt_stats(conn, attempt_id=int(state.attempt_id))

    raw_question = get_next_question(
        conn,
        user_id=state.user_id,
        cat_feature_enabled=True,
    )
    if raw_question is None:
        finished = finish_active_attempt(conn, user_id=state.user_id, completion_reason="items_exhausted")
        next_state = finish_session(state)
        return next_state, finished if finished is not None else {"status": "finished", "attempt_id": state.attempt_id}

    next_state = set_current_question(state, item_id=int(raw_question["item_id"]))

    legacy_payload = build_question_payload(
        conn,
        item_id=int(next_state.current_item_id),
        attempt_id=int(next_state.attempt_id),
    )

    return next_state, _merge_cat_question_fields(
        legacy_payload=legacy_payload,
        raw_question=raw_question,
    )


def submit_choice_and_continue_toggle(
    conn: sqlite3.Connection,
    *,
    state: VocabSessionState,
    choice_id: int,
    cat_live_enabled: bool = False,
) -> tuple[VocabSessionState, dict[str, object]]:
    if not cat_live_enabled:
        return submit_choice_and_continue(conn, state=state, choice_id=choice_id)

    if state.attempt_id is None or state.current_item_id is None:
        raise RuntimeError("no_active_question")

    result = submit_choice(
        conn,
        user_id=state.user_id,
        attempt_id=int(state.attempt_id),
        item_id=int(state.current_item_id),
        choice_id=int(choice_id),
        cat_feature_enabled=True,
    )
    next_state = clear_current_question(state)
    return next_state, result
