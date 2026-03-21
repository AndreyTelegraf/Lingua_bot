from __future__ import annotations

import sqlite3

from services.cat_runtime import (
    CATItemModel,
    answer_cat_session_runtime,
    list_cat_session_events,
    load_cat_session_runtime,
    start_cat_session_runtime,
)


def _conn() -> sqlite3.Connection:
    return sqlite3.connect(":memory:")


def _item(item_id: int, difficulty_b: float = 0.0) -> CATItemModel:
    return CATItemModel(
        item_id=item_id,
        mode="vocab",
        modality="mcq",
        prompt_text=f"prompt-{item_id}",
        answer_key=f"answer-{item_id}",
        difficulty_b=difficulty_b,
        discrimination_a=1.0,
        guessing_c=0.2,
        upper_d=0.95,
        cefr_target="A2",
        content_tag="core",
        skill_tag="lexis",
        is_active=True,
    )


def test_start_runtime_creates_session_and_first_planned_item() -> None:
    conn = _conn()
    try:
        bank = [_item(10, -0.4), _item(20, 0.1), _item(30, 0.7)]

        started = start_cat_session_runtime(
            conn,
            session_id="sess-rt-1",
            user_id=123,
            modality="vocab",
            item_bank=bank,
            started_at="2026-03-21T12:35:00Z",
            metadata={"source": "runtime-test"},
        )

        assert started.session.session_id == "sess-rt-1"
        assert started.step.action in {"ask", "stop"}

        loaded = load_cat_session_runtime(conn, session_id="sess-rt-1")
        assert loaded is not None
        assert loaded.session_id == "sess-rt-1"
        assert loaded.status in {"in_progress", "finished"}

        events = list_cat_session_events(conn, session_id="sess-rt-1")
        assert events[0]["event_type"] == "session_started"
        assert events[1]["event_type"] in {"item_planned", "session_stopped"}
    finally:
        conn.close()


def test_answer_runtime_persists_answer_and_next_plan() -> None:
    conn = _conn()
    try:
        bank = [_item(10, -0.4), _item(20, 0.1), _item(30, 0.7)]

        started = start_cat_session_runtime(
            conn,
            session_id="sess-rt-2",
            user_id=123,
            modality="vocab",
            item_bank=bank,
        )
        assert started.step.action == "ask"
        first_item = started.step.next_item
        assert first_item is not None

        step = answer_cat_session_runtime(
            conn,
            session_id="sess-rt-2",
            item=first_item,
            response_value=1,
            is_correct=True,
            item_bank=bank,
            updated_at="2026-03-21T12:36:00Z",
        )

        loaded = load_cat_session_runtime(conn, session_id="sess-rt-2")
        assert loaded is not None
        assert loaded.items_administered == [first_item.item_id]
        assert len(loaded.answers) == 1
        assert loaded.theta is not None
        assert loaded.se is not None

        events = list_cat_session_events(conn, session_id="sess-rt-2")
        assert [e["event_type"] for e in events[:3]] == [
            "session_started",
            "item_planned",
            "answer_recorded",
        ]
        assert events[-1]["event_type"] in {"item_planned", "session_stopped"}

        if step.action == "ask":
            assert step.next_item is not None
            assert step.next_item.item_id != first_item.item_id
    finally:
        conn.close()


def test_answer_runtime_fails_for_missing_session() -> None:
    conn = _conn()
    try:
        bank = [_item(10)]
        try:
            answer_cat_session_runtime(
                conn,
                session_id="missing",
                item=bank[0],
                response_value=1,
                is_correct=True,
                item_bank=bank,
            )
        except ValueError as exc:
            assert "session not found" in str(exc)
        else:
            raise AssertionError("expected ValueError for missing session")
    finally:
        conn.close()


def test_start_runtime_rejects_duplicate_session_id() -> None:
    conn = _conn()
    try:
        bank = [_item(10), _item(20)]

        first = start_cat_session_runtime(
            conn,
            session_id="sess-dup",
            user_id=1,
            modality="vocab",
            item_bank=bank,
        )
        assert first.session.session_id == "sess-dup"

        try:
            start_cat_session_runtime(
                conn,
                session_id="sess-dup",
                user_id=2,
                modality="vocab",
                item_bank=bank,
            )
        except ValueError as exc:
            assert "session_id already exists" in str(exc)
        else:
            raise AssertionError("expected duplicate session_id error")
    finally:
        conn.close()
