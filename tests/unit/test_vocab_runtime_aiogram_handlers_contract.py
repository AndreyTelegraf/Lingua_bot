from __future__ import annotations

import sqlite3

from services.vocab_runtime.aiogram_handlers_contract import callback_handler_contract, start_handler_contract


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
        'CREATE TABLE vocab_attempts (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, finished_at TEXT, status TEXT NOT NULL DEFAULT started, total_questions INTEGER DEFAULT 0, correct_answers INTEGER DEFAULT 0, UNIQUE(user_id, started_at))'
    )
    conn.execute(
        'CREATE TABLE vocab_attempt_events (id INTEGER PRIMARY KEY AUTOINCREMENT, attempt_id INTEGER NOT NULL, user_id INTEGER NOT NULL, item_id INTEGER NOT NULL, event_type TEXT NOT NULL, answer_text TEXT, is_correct INTEGER, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(attempt_id) REFERENCES vocab_attempts(id))'
    )

    conn.executemany(
        'INSERT INTO vocab_items (id, lemma, question_text, correct_answer, pos, is_active) VALUES (?, ?, ?, ?, ?, ?)',
        [
            (1, 'casa', 'casa', 'дом', 'noun', 1),
            (2, 'janela', 'janela', 'окно', 'noun', 1),
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


def test_aiogram_handlers_contract_happy_path() -> None:
    conn = _conn()
    try:
        start = start_handler_contract(conn=conn, user_id=42)
        fsm = start['fsm']
        assert start['text'] == 'casa'
        assert len(start['keyboard']) == 6

        step1 = callback_handler_contract(conn=conn, fsm=fsm, callback_data='vocab:pick:101')
        fsm = step1['fsm']
        assert step1['answer_result']['is_correct'] is True
        assert step1['text'] == 'janela'

        step2 = callback_handler_contract(conn=conn, fsm=fsm, callback_data='vocab:pick:201')
        assert step2['answer_result']['is_correct'] is False
        assert "Вы правильно ответили на 1 вопрос из 2." in step2['text']
        assert "Ваш пассивный словарный запас находится в диапазоне от 1 000 до 1 500 слов." in step2['text']
        assert "Ориентировочно это соответствует уровню A2." in step2['text']
        assert "A0 A1 A1+ [A2] B1 B2 C1 C1+" in step2['text']
        assert "Это типичный результат для этого диапазона." in step2['text']
        assert "Выводы этого теста приблизительны, они основаны на частотности слов и точности ваших ответов." in step2['text']
        assert step2['keyboard'] != []
    finally:
        conn.close()
