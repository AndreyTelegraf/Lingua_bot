from __future__ import annotations

from services.vocab_runtime.session_driver import answer_session_view, start_session_view


def start_handler_contract(*, conn, user_id: int) -> dict[str, object]:
    return start_session_view(conn, user_id=user_id)


def callback_handler_contract(*, conn, fsm, callback_data: str) -> dict[str, object]:
    return answer_session_view(conn, fsm=fsm, callback_data=callback_data)
