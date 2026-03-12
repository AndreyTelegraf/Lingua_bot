from __future__ import annotations

import sqlite3

from services.vocab_runtime.flow import answer_choice_step, answer_step, begin_flow, next_step


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row

    conn.execute(
        'CREATE TABLE vocab_items (id INTEGER PRIMARY KEY AUTOINCREMENT, lemma TEXT NOT NULL, question_text TEXT NOT NULL, correct_answer TEXT NOT NULL, pos TEXT, is_active INTEGER NOT NULL DEFAULT 0)'
    )
    conn.execute(
        'CREATE TABLE vocab_attempts (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, finished_at TEXT, status TEXT NOT NULL DEFAULT "started", total_questions INTEGER DEFAULT 0, correct_answers INTEGER DEFAULT 0, UNIQUE(user_id, started_at))'
    )
    conn.execute(
        'CREATE TABLE vocab_attempt_events (id INTEGER PRIMARY KEY AUTOINCREMENT, attempt_id INTEGER NOT NULL, user_id INTEGER NOT NULL, item_id INTEGER NOT NULL, event_type TEXT NOT NULL, answer_text TEXT, is_correct INTEGER, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(attempt_id) REFERENCES vocab_attempts(id))'
    )
    conn.execute(
        'CREATE TABLE vocab_choices (id INTEGER PRIMARY KEY AUTOINCREMENT, item_id INTEGER NOT NULL, choice_text TEXT NOT NULL, is_correct INTEGER NOT NULL, position_index INTEGER NOT NULL)'
    )

    conn.executemany(
        'INSERT INTO vocab_items (lemma, question_text, correct_answer, pos, is_active) VALUES (?, ?, ?, ?, ?)',
        [
            ('casa', 'casa', 'дом', 'noun', 1),
            ('janela', 'janela', 'окно', 'noun', 1),
        ],
    )
    conn.executemany(
        'INSERT INTO vocab_choices (id, item_id, choice_text, is_correct, position_index) VALUES (?, ?, ?, ?, ?)',
        [
            (101, 1, 'дом', 1, 1),
            (102, 1, 'окно', 0, 2),
            (103, 1, 'книга', 0, 3),
            (104, 1, 'вода', 0, 4),
            (105, 1, 'стол', 0, 5),
            (106, 1, 'дорога', 0, 6),
            (201, 2, 'дом', 0, 1),
            (202, 2, 'окно', 1, 2),
            (203, 2, 'книга', 0, 3),
            (204, 2, 'вода', 0, 4),
            (205, 2, 'стол', 0, 5),
            (206, 2, 'дорога', 0, 6),
        ],
    )
    conn.commit()
    return conn


def test_flow_happy_path() -> None:
    conn = _conn()
    try:
        state = begin_flow(conn, user_id=42)
        assert state.status == 'in_progress'
        assert state.attempt_id is not None
        assert state.current_item_id is None

        state, q1 = next_step(conn, state=state)
        assert q1 is not None
        assert q1['item_id'] == 1
        assert state.current_item_id == 1

        state, r1 = answer_step(conn, state=state, answer_text='дом')
        assert r1['is_correct'] is True
        assert state.current_item_id is None

        state, q2 = next_step(conn, state=state)
        assert q2 is not None
        assert q2['item_id'] == 2
        assert state.current_item_id == 2

        state, r2 = answer_step(conn, state=state, answer_text='неверно')
        assert r2['is_correct'] is False
        assert state.current_item_id is None

        state, finished = next_step(conn, state=state)
        assert finished is not None
        assert finished['status'] == 'finished'
        assert finished['total_questions'] == 2
        assert finished['correct_answers'] == 1
        assert state.status == 'finished'
    finally:
        conn.close()


def test_flow_rejects_answer_without_active_question() -> None:
    conn = _conn()
    try:
        state = begin_flow(conn, user_id=42)
        try:
            answer_step(conn, state=state, answer_text="дом")
            assert False, "expected RuntimeError"
        except RuntimeError as e:
            assert str(e) == "no_active_question"
    finally:
        conn.close()



def test_flow_choice_happy_path() -> None:
    conn = _conn()
    try:
        state = begin_flow(conn, user_id=77)

        state, q1 = next_step(conn, state=state)
        assert q1 is not None
        assert q1['item_id'] == 1

        state, r1 = answer_choice_step(conn, state=state, choice_id=101)
        assert r1['is_correct'] is True
        assert r1['selected_answer'] == 'дом'
        assert state.current_item_id is None

        state, q2 = next_step(conn, state=state)
        assert q2 is not None
        assert q2['item_id'] == 2

        state, r2 = answer_choice_step(conn, state=state, choice_id=201)
        assert r2['is_correct'] is False
        assert r2['selected_answer'] == 'дом'
        assert r2['total_questions'] == 2
        assert r2['correct_answers'] == 1
    finally:
        conn.close()
