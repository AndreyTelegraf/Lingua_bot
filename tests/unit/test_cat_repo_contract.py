from __future__ import annotations

import sqlite3

from services.cat_runtime import (
    CATEstimate,
    append_answer,
    create_cat_session,
    finish_cat_session,
)
from services.cat_runtime.item_model import CATItemModel
from services.cat_runtime.repo import (
    append_cat_session_event,
    ensure_cat_runtime_tables,
    list_cat_session_events,
    load_cat_session,
    save_cat_session,
)


def _conn() -> sqlite3.Connection:
    return sqlite3.connect(":memory:")


def _item(item_id: int) -> CATItemModel:
    return CATItemModel(
        item_id=item_id,
        mode="vocab",
        modality="mcq",
        prompt_text=f"prompt-{item_id}",
        answer_key=f"answer-{item_id}",
        difficulty_b=0.0,
        discrimination_a=1.0,
        guessing_c=0.2,
        upper_d=0.95,
        cefr_target="A2",
        content_tag="core",
        skill_tag="lexis",
        is_active=True,
    )


def test_save_and_load_cat_session_roundtrip() -> None:
    conn = _conn()
    try:
        ensure_cat_runtime_tables(conn)

        s = create_cat_session(
            session_id="sess-1",
            user_id=123,
            modality="vocab",
            started_at="2026-03-21T12:30:00Z",
            metadata={"source": "repo-test"},
        )
        est = CATEstimate(
            theta=0.45,
            se=0.26,
            information=14.8,
            items_answered=1,
            converged=True,
        )
        append_answer(
            s,
            item=_item(10),
            response_value=1,
            is_correct=True,
            estimate_after=est,
            updated_at="2026-03-21T12:31:00Z",
        )

        save_cat_session(conn, s)
        loaded = load_cat_session(conn, session_id="sess-1")

        assert loaded is not None
        assert loaded.session_id == "sess-1"
        assert loaded.user_id == 123
        assert loaded.modality == "vocab"
        assert loaded.theta == 0.45
        assert loaded.se == 0.26
        assert loaded.items_administered == [10]
        assert len(loaded.answers) == 1
        assert loaded.answers[0].item_id == 10
    finally:
        conn.close()


def test_save_cat_session_updates_existing_row() -> None:
    conn = _conn()
    try:
        s = create_cat_session(session_id="sess-2", user_id=123, modality="vocab")
        save_cat_session(conn, s)

        s.theta = 0.77
        s.se = 0.19
        save_cat_session(conn, s)

        loaded = load_cat_session(conn, session_id="sess-2")
        assert loaded is not None
        assert loaded.theta == 0.77
        assert loaded.se == 0.19

        row = conn.execute("SELECT COUNT(*) FROM cat_sessions WHERE session_id = 'sess-2'").fetchone()
        assert int(row[0]) == 1
    finally:
        conn.close()


def test_append_and_list_cat_session_events() -> None:
    conn = _conn()
    try:
        event_id1 = append_cat_session_event(
            conn,
            session_id="sess-3",
            event_type="session_started",
            payload={"user_id": 123, "modality": "vocab"},
        )
        event_id2 = append_cat_session_event(
            conn,
            session_id="sess-3",
            event_type="answer_recorded",
            payload={"item_id": 10, "is_correct": True},
        )

        events = list_cat_session_events(conn, session_id="sess-3")
        assert [e["id"] for e in events] == [event_id1, event_id2]
        assert events[0]["event_type"] == "session_started"
        assert events[1]["payload"]["item_id"] == 10
    finally:
        conn.close()


def test_finished_session_persists_finished_status() -> None:
    conn = _conn()
    try:
        s = create_cat_session(session_id="sess-4", user_id=777, modality="vocab")
        final_est = CATEstimate(
            theta=-0.12,
            se=0.18,
            information=30.8,
            items_answered=8,
            converged=True,
        )
        finish_cat_session(
            s,
            final_estimate=final_est,
            finished_at="2026-03-21T12:40:00Z",
        )
        s.metadata["stop_reason"] = "target_se_reached"
        save_cat_session(conn, s)

        row = conn.execute(
            "SELECT status FROM cat_sessions WHERE session_id = ?",
            ("sess-4",),
        ).fetchone()
        assert row is not None
        assert row[0] == "finished"

        loaded = load_cat_session(conn, session_id="sess-4")
        assert loaded is not None
        assert loaded.status == "finished"
        assert loaded.theta == -0.12
        assert loaded.se == 0.18
    finally:
        conn.close()
