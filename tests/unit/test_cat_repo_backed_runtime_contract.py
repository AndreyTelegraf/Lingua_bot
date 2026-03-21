from __future__ import annotations

import sqlite3

from services.cat_runtime import (
    answer_cat_session_runtime,
    load_cat_session_runtime,
    start_cat_session_runtime,
)
from services.cat_runtime.repo import list_cat_session_events


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE vocab_items (
            id INTEGER PRIMARY KEY,
            lemma TEXT,
            question_text TEXT,
            correct_answer TEXT,
            freq_rank INTEGER,
            bin_name TEXT,
            level TEXT,
            topic_tag TEXT,
            pos TEXT,
            is_active INTEGER,
            difficulty_b REAL
        )
        """
    )
    return conn


def _seed_vocab(conn: sqlite3.Connection) -> None:
    conn.executemany(
        """
        INSERT INTO vocab_items
        (id, lemma, question_text, correct_answer, freq_rank, bin_name, level, topic_tag, pos, is_active, difficulty_b)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (10, "casa", "Choose casa", "house", 100, "1K", "A1", "home", "noun", 1, -0.5),
            (20, "abrir", "Choose abrir", "open", 1200, "2K", "A2", "verbs", "verb", 1, 0.2),
            (30, "ilha", "Choose ilha", "island", 1800, "2K", "A2", "travel", "noun", 1, 0.7),
        ],
    )
    conn.commit()


def test_start_runtime_can_load_bank_from_repo_when_item_bank_omitted() -> None:
    conn = _conn()
    try:
        _seed_vocab(conn)

        started = start_cat_session_runtime(
            conn,
            session_id="sess-rb-1",
            user_id=123,
            modality="vocab",
            started_at="2026-03-21T13:30:00Z",
            metadata={"source": "repo-backed"},
        )

        assert started.step.action == "ask"
        assert started.step.next_item is not None
        assert started.step.next_item.item_id in {10, 20, 30}

        loaded = load_cat_session_runtime(conn, session_id="sess-rb-1")
        assert loaded is not None
        assert loaded.session_id == "sess-rb-1"

        events = list_cat_session_events(conn, session_id="sess-rb-1")
        assert [e["event_type"] for e in events] == ["session_started", "item_planned"]
        assert events[0]["payload"]["bank_size"] == 3
    finally:
        conn.close()


def test_answer_runtime_can_load_bank_from_repo_when_item_bank_omitted() -> None:
    conn = _conn()
    try:
        _seed_vocab(conn)

        started = start_cat_session_runtime(
            conn,
            session_id="sess-rb-2",
            user_id=123,
            modality="vocab",
        )
        first_item = started.step.next_item
        assert first_item is not None

        step = answer_cat_session_runtime(
            conn,
            session_id="sess-rb-2",
            item=first_item,
            response_value=1,
            is_correct=True,
            updated_at="2026-03-21T13:31:00Z",
        )

        assert step.action in {"ask", "stop"}

        loaded = load_cat_session_runtime(conn, session_id="sess-rb-2")
        assert loaded is not None
        assert loaded.items_administered == [int(first_item.item_id)]
        assert len(loaded.answers) == 1

        events = list_cat_session_events(conn, session_id="sess-rb-2")
        event_types = [e["event_type"] for e in events]
        assert event_types[0] == "session_started"
        assert "answer_recorded" in event_types
        assert event_types[-1] in {"item_planned", "session_stopped"}
    finally:
        conn.close()


def test_start_runtime_raises_when_repo_bank_is_empty() -> None:
    conn = _conn()
    try:
        try:
            start_cat_session_runtime(
                conn,
                session_id="sess-rb-empty",
                user_id=1,
                modality="vocab",
            )
        except ValueError as exc:
            assert "cat item bank is empty" in str(exc)
        else:
            raise AssertionError("expected ValueError for empty CAT bank")
    finally:
        conn.close()
