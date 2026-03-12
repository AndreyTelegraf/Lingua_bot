from __future__ import annotations

from services.vocab_runtime.entrypoints import run_vocab_callback, run_vocab_start


def handle_vocab_start(*, conn, user_id: int) -> dict[str, object]:
    out = run_vocab_start(conn=conn, user_id=user_id)
    return {
        'ok': True,
        'fsm': out['fsm'],
        'text': out['text'],
        'keyboard': out['keyboard'],
        'finished': False,
    }


def handle_vocab_callback(*, conn, fsm, callback_data: str) -> dict[str, object]:
    out = run_vocab_callback(conn=conn, fsm=fsm, callback_data=callback_data)

    finished = out.get('text', '').startswith('Vocab finished.')
    return {
        'ok': True,
        'fsm': out['fsm'],
        'text': out['text'],
        'keyboard': out.get('keyboard', []),
        'answer_result': out.get('answer_result'),
        'finished': finished,
    }
