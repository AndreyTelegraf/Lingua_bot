from __future__ import annotations

from services.vocab_runtime.handler_layer import handle_vocab_callback, handle_vocab_start


def vocab_v2_start(*, conn, store, user_id: int) -> dict[str, object]:
    out = handle_vocab_start(conn=conn, user_id=user_id)
    store.set(user_id=user_id, fsm=out['fsm'])
    return out


def vocab_v2_callback(*, conn, store, user_id: int, callback_data: str) -> dict[str, object]:
    fsm = store.get(user_id=user_id)

    if fsm is None:
        return {
            'ok': False,
            'error': 'fsm_not_found',
            'text': 'Session not found. Start again.',
            'keyboard': [],
            'finished': True,
        }

    out = handle_vocab_callback(conn=conn, fsm=fsm, callback_data=callback_data)

    if out['finished']:
        store.clear(user_id=user_id)
    else:
        store.set(user_id=user_id, fsm=out['fsm'])

    return out
