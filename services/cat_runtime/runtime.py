from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Sequence

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


def start_cat_session_runtime(
    conn: sqlite3.Connection,
    *,
    session_id: str,
    user_id: int,
    modality: str,
    item_bank: Sequence[CATItemModel],
    started_at: str | None = None,
    metadata: dict | None = None,
) -> CATStartResult:
    ensure_cat_runtime_tables(conn)

    existing = load_cat_session(conn, session_id=session_id)
    if existing is not None:
        raise ValueError("session_id already exists")

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
        session_id=session.session_id,
        event_type="session_started",
        payload={
            "user_id": session.user_id,
            "modality": session.modality,
            "started_at": session.started_at,
        },
    )

    step = plan_next_cat_step(session, candidate_items=item_bank)
    save_cat_session(conn, session)

    if step.action == "ask" and step.next_item is not None:
        append_cat_session_event(
            conn,
            session_id=session.session_id,
            event_type="item_planned",
            payload={
                "item_id": step.next_item.item_id,
                "theta": None if step.estimate is None else step.estimate.theta,
                "se": None if step.estimate is None else step.estimate.se,
            },
        )
    elif step.action == "stop":
        append_cat_session_event(
            conn,
            session_id=session.session_id,
            event_type="session_stopped",
            payload={
                "reason": step.stop_reason,
                "theta": None if step.estimate is None else step.estimate.theta,
                "se": None if step.estimate is None else step.estimate.se,
            },
        )

    return CATStartResult(session=session, step=step)


def answer_cat_session_runtime(
    conn: sqlite3.Connection,
    *,
    session_id: str,
    item: CATItemModel,
    response_value: int | float,
    is_correct: bool,
    item_bank: Sequence[CATItemModel],
    updated_at: str | None = None,
) -> CATOrchestrationStep:
    ensure_cat_runtime_tables(conn)

    session = load_cat_session(conn, session_id=session_id)
    if session is None:
        raise ValueError("session not found")

    step = record_answer_and_plan_next(
        session,
        item=item,
        response_value=response_value,
        is_correct=is_correct,
        item_bank=item_bank,
        updated_at=updated_at,
    )
    save_cat_session(conn, session)

    append_cat_session_event(
        conn,
        session_id=session.session_id,
        event_type="answer_recorded",
        payload={
            "item_id": item.item_id,
            "response_value": response_value,
            "is_correct": bool(is_correct),
            "theta": None if step.estimate is None else step.estimate.theta,
            "se": None if step.estimate is None else step.estimate.se,
        },
    )

    if step.action == "ask" and step.next_item is not None:
        append_cat_session_event(
            conn,
            session_id=session.session_id,
            event_type="item_planned",
            payload={
                "item_id": step.next_item.item_id,
                "theta": None if step.estimate is None else step.estimate.theta,
                "se": None if step.estimate is None else step.estimate.se,
            },
        )
    elif step.action == "stop":
        append_cat_session_event(
            conn,
            session_id=session.session_id,
            event_type="session_stopped",
            payload={
                "reason": step.stop_reason,
                "theta": None if step.estimate is None else step.estimate.theta,
                "se": None if step.estimate is None else step.estimate.se,
            },
        )

    return step


def load_cat_session_runtime(
    conn: sqlite3.Connection,
    *,
    session_id: str,
) -> CATSessionState | None:
    ensure_cat_runtime_tables(conn)
    return load_cat_session(conn, session_id=session_id)
