from __future__ import annotations
import uuid

import sqlite3

from services.vocab_runtime.repo import (
    finish_attempt,
    get_active_attempt,
    get_attempt_stats,
    log_event,
    persist_finished_result,
    start_attempt,
)
from services.vocab_runtime.selector import get_next_item
from services.cat_runtime import build_cat_runtime_native_payload


def _start_or_resume_attempt_legacy(conn: sqlite3.Connection, *, user_id: int) -> dict[str, object]:
    mode_run_id = str(uuid.uuid4())
    attempt_id = start_attempt(conn, user_id=user_id, mode_run_id=mode_run_id)
    return get_attempt_stats(conn, attempt_id=attempt_id)


def _get_next_question_legacy(conn: sqlite3.Connection, *, user_id: int) -> dict[str, object] | None:
    active = get_active_attempt(conn, user_id=user_id)
    if active is None:
        attempt_id = start_attempt(conn, user_id=user_id, mode_run_id=str(uuid.uuid4()))
    else:
        attempt_id = int(active["id"])

    item = get_next_item(conn, attempt_id=attempt_id)
    if item is None:
        return None

    log_event(
        conn,
        attempt_id=attempt_id,
        user_id=user_id,
        item_id=int(item["id"]),
        event_type="shown",
    )

    return {
        "attempt_id": attempt_id,
        "item_id": int(item["id"]),
        "lemma": str(item["lemma"]),
        "question_text": str(item["question_text"]),
        "correct_answer": str(item["correct_answer"]),
        "pos": str(item["pos"] or ""),
    }


def _submit_answer_legacy(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    attempt_id: int,
    item_id: int,
    answer_text: str | None,
) -> dict[str, object]:
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT correct_answer FROM vocab_items_runtime_v3 WHERE id = ?",
        (item_id,),
    ).fetchone()
    if row is None:
        raise RuntimeError("item_not_found")

    correct_answer = str(row["correct_answer"])
    is_correct = 1 if (answer_text or "").strip().casefold() == correct_answer.strip().casefold() else 0

    log_event(
        conn,
        attempt_id=attempt_id,
        user_id=user_id,
        item_id=item_id,
        event_type="answer",
        answer_text=answer_text,
        is_correct=is_correct,
    )

    stats = get_attempt_stats(conn, attempt_id=attempt_id)
    return {
        "is_correct": bool(is_correct),
        "correct_answer": correct_answer,
        "total_questions": stats["total_questions"],
        "correct_answers": stats["correct_answers"],
        "wrong_answers": stats["wrong_answers"],
        "accuracy_pct": stats["accuracy_pct"],
        "estimated_vocab_size": stats.get("estimated_vocab_size"),
        "estimated_vocab_band": stats.get("estimated_vocab_band"),
        "confidence": stats.get("confidence"),
        "coverage_score": stats.get("coverage_score"),
        "difficulty_score": stats.get("difficulty_score"),
        "spread_score": stats.get("spread_score"),
        "sample_score": stats.get("sample_score"),
        "scoring_model": stats.get("scoring_model"),
    }


def finish_active_attempt(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    completion_reason: str = "items_exhausted",
) -> dict[str, object] | None:
    active = get_active_attempt(conn, user_id=user_id)
    if active is None:
        return None

    attempt_id = int(active["id"])
    finish_attempt(conn, attempt_id=attempt_id, completion_reason=completion_reason)
    return persist_finished_result(conn, attempt_id=attempt_id)


def _submit_choice_legacy(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    attempt_id: int,
    item_id: int,
    choice_id: int,
) -> dict[str, object]:
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT choice_text, is_correct FROM vocab_choices_v3 WHERE id = ? AND item_id = ?",
        (choice_id, item_id),
    ).fetchone()
    if row is None:
        raise RuntimeError("choice_not_found")

    answer_text = str(row["choice_text"])
    is_correct = int(row["is_correct"])

    log_event(
        conn,
        attempt_id=attempt_id,
        user_id=user_id,
        item_id=item_id,
        event_type="answer",
        answer_text=answer_text,
        is_correct=is_correct,
    )

    stats = get_attempt_stats(conn, attempt_id=attempt_id)
    return {
        "is_correct": bool(is_correct),
        "correct_answer": answer_text if is_correct else None,
        "selected_answer": answer_text,
        "total_questions": stats["total_questions"],
        "correct_answers": stats["correct_answers"],
        "wrong_answers": stats["wrong_answers"],
        "accuracy_pct": stats["accuracy_pct"],
        "estimated_vocab_size": stats.get("estimated_vocab_size"),
        "estimated_vocab_band": stats.get("estimated_vocab_band"),
        "confidence": stats.get("confidence"),
        "coverage_score": stats.get("coverage_score"),
        "difficulty_score": stats.get("difficulty_score"),
        "spread_score": stats.get("spread_score"),
        "sample_score": stats.get("sample_score"),
        "scoring_model": stats.get("scoring_model"),
    }


# ===== CAT layer 19: real vocab service integration seam =====

def maybe_start_cat_from_vocab_service(
    conn,
    *,
    user_id: int,
    attempt_id: int,
    feature_enabled: bool,
    item_bank=None,
    started_at: str | None = None,
    metadata: dict | None = None,
    active_only: bool = True,
    limit: int | None = None,
):
    from services.cat_runtime import patchable_start_from_vocab_runtime

    return patchable_start_from_vocab_runtime(
        conn,
        user_id=int(user_id),
        attempt_id=int(attempt_id),
        feature_enabled=feature_enabled,
        item_bank=item_bank,
        started_at=started_at,
        metadata=metadata,
        active_only=active_only,
        limit=limit,
    )


def maybe_continue_cat_from_vocab_service_answer(
    conn,
    *,
    user_id: int,
    attempt_id: int,
    feature_enabled: bool,
    item,
    response_value: int | float,
    is_correct: bool,
    item_bank=None,
    updated_at: str | None = None,
    metadata: dict | None = None,
):
    from services.cat_runtime import patchable_answer_from_vocab_runtime

    return patchable_answer_from_vocab_runtime(
        conn,
        user_id=int(user_id),
        attempt_id=int(attempt_id),
        feature_enabled=feature_enabled,
        item=item,
        response_value=response_value,
        is_correct=is_correct,
        item_bank=item_bank,
        updated_at=updated_at,
        metadata=metadata,
    )

# ===== CAT layer 20: patch real vocab service entrypoints =====

def _cat_service_feature_enabled(flag_value) -> bool:
    return bool(flag_value)


def _cat_route_source(cat_route) -> str | None:
    if cat_route is None:
        return None
    source = getattr(cat_route, "source", None)
    if source is None and isinstance(cat_route, dict):
        source = cat_route.get("source")
    return None if source is None else str(source)


def _cat_route_runtime_native_payload(cat_route) -> dict[str, object] | None:
    if cat_route is None:
        return None

    route_result = getattr(cat_route, "route_result", None)
    if route_result is None and isinstance(cat_route, dict):
        route_result = cat_route.get("route_result")

    result = getattr(route_result, "result", None)
    if result is None and isinstance(route_result, dict):
        result = route_result.get("result")

    cat_started = getattr(result, "cat_started", None)
    if cat_started is None and isinstance(result, dict):
        cat_started = result.get("cat_started")

    payload = getattr(cat_started, "payload", None)
    if payload is None and isinstance(cat_started, dict):
        payload = cat_started.get("payload")

    if payload is None and cat_started is not None:
        session = getattr(cat_started, "session", None)
        if session is None and isinstance(cat_started, dict):
            session = cat_started.get("session")

        step = getattr(cat_started, "step", None)
        if step is None and isinstance(cat_started, dict):
            step = cat_started.get("step")

        if session is not None and step is not None:
            payload = build_cat_runtime_native_payload(
                session=session,
                step=step,
                mode=str(getattr(session, "modality", "vocab")),
            )

    if payload is None:
        return None

    out = {
        "kind": getattr(payload, "kind", None),
        "mode": getattr(payload, "mode", None),
        "session_id": getattr(payload, "session_id", None),
        "status": getattr(payload, "status", None),
        "theta": getattr(payload, "theta", None),
        "se": getattr(payload, "se", None),
        "item_id": getattr(payload, "item_id", None),
        "prompt_text": getattr(payload, "prompt_text", None),
        "answer_key": getattr(payload, "answer_key", None),
        "stop_reason": getattr(payload, "stop_reason", None),
        "payload_version": getattr(payload, "payload_version", "cat_runtime_payload_v1"),
    }

    if not out["kind"]:
        return None

    return out


def _attach_cat_route(result, cat_route):
    if not isinstance(result, dict):
        return result

    out = dict(result)
    out["cat_route"] = cat_route

    source = _cat_route_source(cat_route)
    if source == "cat":
        out.setdefault("runtime_branch", "cat")
        out.setdefault("cat_native", True)
        out.setdefault("visible_mode", "cat")
        out.setdefault("visible_semantics", "adaptive")

    native = _cat_route_runtime_native_payload(cat_route)
    if native is not None:
        out["runtime_branch"] = "cat"
        out["runtime_native_payload"] = native
        out["cat_native"] = True
        out["visible_mode"] = "cat"
        out["visible_semantics"] = "adaptive"
        out["cat_payload_kind"] = native.get("kind")

    return out


def start_or_resume_attempt(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    cat_feature_enabled: bool = False,
    item_bank=None,
    started_at: str | None = None,
    metadata: dict | None = None,
    active_only: bool = True,
    limit: int | None = None,
) -> dict[str, object]:
    result = _start_or_resume_attempt_legacy(conn, user_id=user_id)

    if not _cat_service_feature_enabled(cat_feature_enabled):
        return result

    attempt_id = int(result["attempt_id"])
    cat_route = maybe_start_cat_from_vocab_service(
        conn,
        user_id=int(user_id),
        attempt_id=attempt_id,
        feature_enabled=True,
        item_bank=item_bank,
        started_at=started_at,
        metadata=metadata,
        active_only=active_only,
        limit=limit,
    )
    return _attach_cat_route(result, cat_route)


def get_next_question(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    cat_feature_enabled: bool = False,
    item_bank=None,
    started_at: str | None = None,
    metadata: dict | None = None,
    active_only: bool = True,
    limit: int | None = None,
) -> dict[str, object] | None:
    result = _get_next_question_legacy(conn, user_id=user_id)

    if result is None or not _cat_service_feature_enabled(cat_feature_enabled):
        return result

    attempt_id = int(result["attempt_id"])
    cat_route = maybe_start_cat_from_vocab_service(
        conn,
        user_id=int(user_id),
        attempt_id=attempt_id,
        feature_enabled=True,
        item_bank=item_bank,
        started_at=started_at,
        metadata=metadata,
        active_only=active_only,
        limit=limit,
    )
    return _attach_cat_route(result, cat_route)


def submit_answer(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    attempt_id: int,
    item_id: int,
    answer_text: str | None,
    cat_feature_enabled: bool = False,
    item=None,
    response_value: int | float | None = None,
    is_correct: bool | None = None,
    item_bank=None,
    updated_at: str | None = None,
    metadata: dict | None = None,
) -> dict[str, object]:
    result = _submit_answer_legacy(
        conn,
        user_id=user_id,
        attempt_id=attempt_id,
        item_id=item_id,
        answer_text=answer_text,
    )

    if not _cat_service_feature_enabled(cat_feature_enabled) or item is None:
        return result

    effective_response = 1 if bool(result.get("is_correct")) else 0
    if response_value is not None:
        effective_response = response_value

    effective_correct = bool(result.get("is_correct")) if is_correct is None else bool(is_correct)

    cat_route = maybe_continue_cat_from_vocab_service_answer(
        conn,
        user_id=int(user_id),
        attempt_id=int(attempt_id),
        feature_enabled=True,
        item=item,
        response_value=effective_response,
        is_correct=effective_correct,
        item_bank=item_bank,
        updated_at=updated_at,
        metadata=metadata,
    )
    return _attach_cat_route(result, cat_route)


def submit_choice(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    attempt_id: int,
    item_id: int,
    choice_id: int,
    cat_feature_enabled: bool = False,
    item=None,
    response_value: int | float | None = None,
    is_correct: bool | None = None,
    item_bank=None,
    updated_at: str | None = None,
    metadata: dict | None = None,
) -> dict[str, object]:
    result = _submit_choice_legacy(
        conn,
        user_id=user_id,
        attempt_id=attempt_id,
        item_id=item_id,
        choice_id=choice_id,
    )

    if not _cat_service_feature_enabled(cat_feature_enabled) or item is None:
        return result

    effective_response = 1 if bool(result.get("is_correct")) else 0
    if response_value is not None:
        effective_response = response_value

    effective_correct = bool(result.get("is_correct")) if is_correct is None else bool(is_correct)

    cat_route = maybe_continue_cat_from_vocab_service_answer(
        conn,
        user_id=int(user_id),
        attempt_id=int(attempt_id),
        feature_enabled=True,
        item=item,
        response_value=effective_response,
        is_correct=effective_correct,
        item_bank=item_bank,
        updated_at=updated_at,
        metadata=metadata,
    )
    return _attach_cat_route(result, cat_route)
