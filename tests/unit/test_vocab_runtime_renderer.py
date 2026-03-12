from __future__ import annotations

import sqlite3

from services.vocab_runtime.renderer import build_question_payload


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row

    conn.execute(
        'CREATE TABLE vocab_items (id INTEGER PRIMARY KEY AUTOINCREMENT, lemma TEXT NOT NULL, question_text TEXT NOT NULL, correct_answer TEXT NOT NULL, pos TEXT, is_active INTEGER NOT NULL DEFAULT 0)'
    )
    conn.execute(
        'CREATE TABLE vocab_choices (id INTEGER PRIMARY KEY AUTOINCREMENT, item_id INTEGER NOT NULL, choice_text TEXT NOT NULL, is_correct INTEGER NOT NULL, position_index INTEGER NOT NULL)'
    )

    conn.execute(
        'INSERT INTO vocab_items (id, lemma, question_text, correct_answer, pos, is_active) VALUES (1, "casa", "casa", "дом", "noun", 1)'
    )
    conn.executemany(
        'INSERT INTO vocab_choices (item_id, choice_text, is_correct, position_index) VALUES (?, ?, ?, ?)',
        [
            (1, 'дом', 1, 1),
            (1, 'окно', 0, 2),
            (1, 'книга', 0, 3),
            (1, 'вода', 0, 4),
            (1, 'стол', 0, 5),
            (1, 'дорога', 0, 6),
        ],
    )
    conn.commit()
    return conn


def test_build_question_payload_happy_path() -> None:
    conn = _conn()
    try:
        payload = build_question_payload(conn, item_id=1, attempt_id=777)
        assert payload['attempt_id'] == 777
        assert payload['item_id'] == 1
        assert payload['lemma'] == 'casa'
        assert payload['question_text'] == 'casa'
        assert payload['pos'] == 'noun'
        assert len(payload['choices']) == 6
        assert [c['position_index'] for c in payload['choices']] == [1, 2, 3, 4, 5, 6]
    finally:
        conn.close()


def test_build_question_payload_rejects_invalid_choice_count() -> None:
    conn = _conn()
    try:
        conn.execute('DELETE FROM vocab_choices WHERE position_index = 6')
        conn.commit()
        try:
            build_question_payload(conn, item_id=1, attempt_id=777)
            assert False, 'expected RuntimeError'
        except RuntimeError as e:
            assert str(e) == 'invalid_choice_count'
    finally:
        conn.close()
