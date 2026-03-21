from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any, Sequence

from .bank_loader import load_cat_item_bank_from_vocab
from .item_model import CATItemModel
from .orchestrator import CATOrchestrationStep, plan_next_cat_step, record_answer_and_plan_next
from .repo import (
    append_cat_session_event,
    ensure_cat_runtime_tables,
    load_cat_session,
    save_cat_session,
)
from .session import CATSessionState, create_cat_session


@dataclass(slots=True)
class CATStartResult:
    session: CATSessionState
    step: CATOrchestrationStep


@dataclass(slots=True)
class CATRuntimeNativePayload:
    kind: str
    mode: str
    session_id: str
    status: str
    theta: float | None
    se: float | None
    item_id: int | None = None
    prompt_text: str | None = None
    answer_key: str | None = None
    stop_reason: str | None = None
    payload_version: str = "cat_runtime_payload_v1"


@dataclass(slots=True)
class CATRuntimeStartResult:
    session: CATSessionState
    step: CATOrchestrationStep
    payload: CATRuntimeNativePayload


@dataclass(slots=True)
class CATRuntimeAnswerResult:
    session: CATSessionState
    step: CATOrchestrationStep
    payload: CATRuntimeNativePayload


def _append_step_event(conn: sqlite3.Connection, *, session_id: str, step: CATOrchestrationStep) -> None:
    if step.action == "ask" and step.next_item is not None:
        append_cat_session_event(
            conn,
            session_id=session_id,
            event_type="item_planned",
            payload={
                "item_id": int(step.next_item.item_id),
                "theta": None if step.estimate is None else float(step.estimate.theta),
                "se": None if step.estimate is None else float(step.estimate.se),
            },
        )
    elif step.action == "stop":
        append_cat_session_event(
            conn,
            session_id=session_id,
            event_type="session_stopped",
            payload={
                "reason": step.stop_reason,
                "theta": None if step.estimate is None else float(step.estimate.theta),
                "se": None if step.estimate is None else float(step.estimate.se),
            },
        )


def _load_bank_or_raise(
    conn: sqlite3.Connection,
    *,
    item_bank: Sequence[CATItemModel] | None = None,
    active_only: bool = True,
    limit: int | None = None,
) -> list[CATItemModel]:
    if item_bank is not None:
        return list(item_bank)
    bank = load_cat_item_bank_from_vocab(
        conn,
        active_only=active_only,
        limit=limit,
    )
    if not bank:
        raise ValueError("cat item bank is empty")
    return bank


def build_cat_runtime_native_payload(
    *,
    session: CATSessionState,
    step: CATOrchestrationStep,
    mode: str = "vocab",
) -> CATRuntimeNativePayload:
    theta = None if step.estimate is None else float(step.estimate.theta)
    se = None if step.estimate is None else float(step.estimate.se)

    if step.action == "ask" and step.next_item is not None:
        return CATRuntimeNativePayload(
            kind="question",
            mode=str(mode),
            session_id=str(session.session_id),
            status=str(session.status),
            theta=theta,
            se=se,
            item_id=int(step.next_item.item_id),
            prompt_text=str(step.next_item.prompt_text),
            answer_key=str(step.next_item.answer_key),
            stop_reason=None,
        )

    if step.action == "stop":
        return CATRuntimeNativePayload(
            kind="result",
            mode=str(mode),
            session_id=str(session.session_id),
            status=str(session.status),
            theta=theta,
            se=se,
            item_id=None,
            prompt_text=None,
            answer_key=None,
            stop_reason=None if step.stop_reason is None else str(step.stop_reason),
        )

    return CATRuntimeNativePayload(
        kind="message",
        mode=str(mode),
        session_id=str(session.session_id),
        status=str(session.status),
        theta=theta,
        se=se,
        item_id=None,
        prompt_text=None,
        answer_key=None,
        stop_reason=None,
    )


def start_cat_session_runtime(
    conn: sqlite3.Connection,
    *,
    session_id: str,
    user_id: int,
    modality: str,
    item_bank: Sequence[CATItemModel] | None = None,
    started_at: str | None = None,
    metadata: dict | None = None,
    active_only: bool = True,
    limit: int | None = None,
) -> CATStartResult:
    ensure_cat_runtime_tables(conn)

    existing = load_cat_session(conn, session_id=session_id)
    if existing is not None:
        raise ValueError("session_id already exists")

    bank = _load_bank_or_raise(
        conn,
        item_bank=item_bank,
        active_only=active_only,
        limit=limit,
    )

    session = create_cat_session(
        session_id=session_id,
        user_id=user_id,
        modality=modality,
        started_at=started_at,
        metadata=metadata or {},
    )
    save_cat_session(conn, session)

    append_cat_session_event(
        conn,
        session_id=session_id,
        event_type="session_started",
        payload={
            "user_id": int(user_id),
            "modality": modality,
            "bank_size": len(bank),
        },
    )

    step = plan_next_cat_step(session, candidate_items=bank)
    save_cat_session(conn, session)
    _append_step_event(conn, session_id=session_id, step=step)
    return CATStartResult(session=session, step=step)


def start_cat_session_runtime_native(
    conn: sqlite3.Connection,
    *,
    session_id: str,
    user_id: int,
    modality: str,
    item_bank: Sequence[CATItemModel] | None = None,
    started_at: str | None = None,
    metadata: dict | None = None,
    active_only: bool = True,
    limit: int | None = None,
) -> CATRuntimeStartResult:
    started = start_cat_session_runtime(
        conn,
        session_id=session_id,
        user_id=user_id,
        modality=modality,
        item_bank=item_bank,
        started_at=started_at,
        metadata=metadata,
        active_only=active_only,
        limit=limit,
    )
    payload = build_cat_runtime_native_payload(
        session=started.session,
        step=started.step,
        mode=modality,
    )
    return CATRuntimeStartResult(
        session=started.session,
        step=started.step,
        payload=payload,
    )


def load_cat_session_runtime(conn: sqlite3.Connection, *, session_id: str) -> CATSessionState | None:
    return load_cat_session(conn, session_id=session_id)


def answer_cat_session_runtime(
    conn: sqlite3.Connection,
    *,
    session_id: str,
    item: CATItemModel,
    response_value: int | float,
    is_correct: bool,
    item_bank: Sequence[CATItemModel] | None = None,
    updated_at: str | None = None,
    active_only: bool = True,
    limit: int | None = None,
) -> CATOrchestrationStep:
    ensure_cat_runtime_tables(conn)

    session = load_cat_session(conn, session_id=session_id)
    if session is None:
        raise ValueError("session not found")

    bank = _load_bank_or_raise(
        conn,
        item_bank=item_bank,
        active_only=active_only,
        limit=limit,
    )

    step = record_answer_and_plan_next(
        session,
        item=item,
        response_value=response_value,
        is_correct=is_correct,
        item_bank=bank,
        updated_at=updated_at,
    )
    save_cat_session(conn, session)

    append_cat_session_event(
        conn,
        session_id=session_id,
        event_type="answer_recorded",
        payload={
            "item_id": int(item.item_id),
            "response_value": float(response_value),
            "is_correct": bool(is_correct),
        },
    )
    _append_step_event(conn, session_id=session_id, step=step)
    return step


def answer_cat_session_runtime_native(
    conn: sqlite3.Connection,
    *,
    session_id: str,
    item: CATItemModel,
    response_value: int | float,
    is_correct: bool,
    item_bank: Sequence[CATItemModel] | None = None,
    updated_at: str | None = None,
    active_only: bool = True,
    limit: int | None = None,
) -> CATRuntimeAnswerResult:
    session = load_cat_session_runtime(conn, session_id=session_id)
    if session is None:
        raise ValueError("session not found")

    step = answer_cat_session_runtime(
        conn,
        session_id=session_id,
        item=item,
        response_value=response_value,
        is_correct=is_correct,
        item_bank=item_bank,
        updated_at=updated_at,
        active_only=active_only,
        limit=limit,
    )
    refreshed = load_cat_session_runtime(conn, session_id=session_id)
    if refreshed is None:
        raise ValueError("session not found after answer")
    payload = build_cat_runtime_native_payload(
        session=refreshed,
        step=step,
        mode=str(refreshed.modality),
    )
    return CATRuntimeAnswerResult(
        session=refreshed,
        step=step,
        payload=payload,
    )
