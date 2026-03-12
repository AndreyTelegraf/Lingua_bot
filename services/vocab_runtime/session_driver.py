from __future__ import annotations

import sqlite3

from services.vocab_runtime.aiogram_glue import handle_callback, handle_start
from services.vocab_runtime.presenter import present_finished, present_question
from services.vocab_runtime.keyboards import finished_keyboard


def start_session_view(conn: sqlite3.Connection, *, user_id: int) -> dict[str, object]:
    out = handle_start(conn, user_id=user_id)
    view = out['view']
    if view is None:
        return {'fsm': out['fsm'], 'text': 'No questions available.', 'keyboard': []}

    if 'status' in view and view['status'] == 'finished':
        return {'fsm': out['fsm'], 'text': present_finished(view), 'keyboard': finished_keyboard(attempt_id=int(view.get("attempt_id")) if view.get("attempt_id") is not None else None), 'finished': True}

    return {
        'fsm': out['fsm'],
        'text': present_question(view),
        'keyboard': view['keyboard'],
    }


def answer_session_view(
    conn: sqlite3.Connection,
    *,
    fsm: object,
    callback_data: str,
) -> dict[str, object]:
    out = handle_callback(conn, fsm=fsm, callback_data=callback_data)
    next_view = out['next_view']

    if next_view is None:
        return {
            'fsm': out['fsm'],
            'answer_result': out['answer_result'],
            'text': 'No next question.',
            'keyboard': [],
        }

    if 'status' in next_view and next_view['status'] == 'finished':
        return {
            'fsm': out['fsm'],
            'answer_result': out['answer_result'],
            'text': present_finished(next_view),
            'keyboard': finished_keyboard(attempt_id=int(next_view.get("attempt_id")) if next_view.get("attempt_id") is not None else None),
            'finished': True,
        }

    return {
        'fsm': out['fsm'],
        'answer_result': out['answer_result'],
        'text': present_question(next_view),
        'keyboard': next_view['keyboard'],
    }
