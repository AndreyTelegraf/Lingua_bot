from __future__ import annotations

from handlers.vocab_v2 import vocab_v2_callback, vocab_v2_start


def register_vocab_v2_routes(*, router, conn_factory, store):
    def start_handler(*, user_id: int) -> dict[str, object]:
        conn = conn_factory()
        try:
            return vocab_v2_start(conn=conn, store=store, user_id=user_id)
        finally:
            conn.close()

    def callback_handler(*, user_id: int, callback_data: str) -> dict[str, object]:
        conn = conn_factory()
        try:
            return vocab_v2_callback(conn=conn, store=store, user_id=user_id, callback_data=callback_data)
        finally:
            conn.close()

    router["vocab_v2_start"] = start_handler
    router["vocab_v2_callback"] = callback_handler
    return router
