from __future__ import annotations

import sqlite3

from services.vocab_runtime.service import (
    finish_active_attempt,
    get_next_question,
    start_or_resume_attempt,
    submit_answer,
)


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

    conn.executemany(
        'INSERT INTO vocab_items (lemma, question_text, correct_answer, pos, is_active) VALUES (?, ?, ?, ?, ?)',
        [
            ('casa', 'casa', 'дом', 'noun', 1),
            ('janela', 'janela', 'окно', 'noun', 1),
            ('livro', 'livro', 'книга', 'noun', 1),
        ],
    )

    conn.commit()
    return conn


def test_service_happy_path() -> None:
    conn = _conn()
    try:
        attempt = start_or_resume_attempt(conn, user_id=42)
        assert attempt['status'] == 'started'

        q1 = get_next_question(conn, user_id=42)
        assert q1 is not None
        assert q1['item_id'] == 1

        r1 = submit_answer(
            conn,
            user_id=42,
            attempt_id=int(q1['attempt_id']),
            item_id=int(q1['item_id']),
            answer_text='дом',
        )
        assert r1['is_correct'] is True
        assert r1['total_questions'] == 1
        assert r1['correct_answers'] == 1

        q2 = get_next_question(conn, user_id=42)
        assert q2 is not None
        assert q2['item_id'] == 2

        r2 = submit_answer(
            conn,
            user_id=42,
            attempt_id=int(q2['attempt_id']),
            item_id=int(q2['item_id']),
            answer_text='неправильный ответ',
        )
        assert r2['is_correct'] is False
        assert r2['total_questions'] == 2
        assert r2['correct_answers'] == 1

        finished = finish_active_attempt(conn, user_id=42)
        assert finished is not None
        assert finished['status'] == 'finished'
        assert finished['total_questions'] == 2
        assert finished['correct_answers'] == 1
    finally:
        conn.close()



def test_submit_choice_happy_path() -> None:
    conn = _conn()
    try:
        conn.execute(
            'CREATE TABLE vocab_choices (id INTEGER PRIMARY KEY AUTOINCREMENT, item_id INTEGER NOT NULL, choice_text TEXT NOT NULL, is_correct INTEGER NOT NULL, position_index INTEGER NOT NULL)'
        )
        conn.executemany(
            'INSERT INTO vocab_choices (id, item_id, choice_text, is_correct, position_index) VALUES (?, ?, ?, ?, ?)',
            [
                (101, 1, 'дом', 1, 1),
                (102, 1, 'окно', 0, 2),
            ],
        )
        conn.commit()

        from services.vocab_runtime.service import submit_choice

        attempt = start_or_resume_attempt(conn, user_id=42)
        result = submit_choice(
            conn,
            user_id=42,
            attempt_id=int(attempt['attempt_id']),
            item_id=1,
            choice_id=101,
        )
        assert result['is_correct'] is True
        assert result['selected_answer'] == 'дом'
        assert result['total_questions'] == 1
        assert result['correct_answers'] == 1
    finally:
        conn.close()


def test_submit_choice_rejects_unknown_choice() -> None:
    conn = _conn()
    try:
        conn.execute(
            'CREATE TABLE vocab_choices (id INTEGER PRIMARY KEY AUTOINCREMENT, item_id INTEGER NOT NULL, choice_text TEXT NOT NULL, is_correct INTEGER NOT NULL, position_index INTEGER NOT NULL)'
        )
        conn.commit()

        from services.vocab_runtime.service import submit_choice

        attempt = start_or_resume_attempt(conn, user_id=42)
        try:
            submit_choice(
                conn,
                user_id=42,
                attempt_id=int(attempt['attempt_id']),
                item_id=1,
                choice_id=999,
            )
            assert False, 'expected RuntimeError'
        except RuntimeError as e:
            assert str(e) == 'choice_not_found'
    finally:
        conn.close()



def test_submit_choice_rejects_choice_from_another_item() -> None:
    conn = _conn()
    try:
        conn.execute(
            'CREATE TABLE vocab_choices (id INTEGER PRIMARY KEY AUTOINCREMENT, item_id INTEGER NOT NULL, choice_text TEXT NOT NULL, is_correct INTEGER NOT NULL, position_index INTEGER NOT NULL)'
        )
        conn.executemany(
            'INSERT INTO vocab_choices (id, item_id, choice_text, is_correct, position_index) VALUES (?, ?, ?, ?, ?)',
            [
                (101, 1, 'дом', 1, 1),
                (201, 2, 'окно', 1, 1),
            ],
        )
        conn.commit()

        from services.vocab_runtime.service import submit_choice

        attempt = start_or_resume_attempt(conn, user_id=42)
        try:
            submit_choice(
                conn,
                user_id=42,
                attempt_id=int(attempt['attempt_id']),
                item_id=1,
                choice_id=201,
            )
            assert False, 'expected RuntimeError'
        except RuntimeError as e:
            assert str(e) == 'choice_not_found'
    finally:
        conn.close()
