from __future__ import annotations

import os
import sqlite3

from services.vocab_runtime.controller import (
    get_next_payload,
    get_next_payload_toggle,
    start_controller,
    start_controller_toggle,
    submit_choice_and_continue,
    submit_choice_and_continue_toggle,
)
from services.vocab_runtime.fsm import VocabFSM, attach_state
from services.vocab_runtime.state import VocabSessionState


def _cat_live_enabled() -> bool:
    raw = str(os.getenv("VOCAB_V2_CAT_LIVE_ENABLED", "")).strip().lower()
    return raw in {"1", "true", "yes", "on"}


def start_vocab_session(conn: sqlite3.Connection, *, user_id: int) -> VocabFSM:
    state = start_controller_toggle(
        conn,
        user_id=user_id,
        cat_live_enabled=_cat_live_enabled(),
    )
    return VocabFSM(state=state)


def get_vocab_question(
    conn: sqlite3.Connection,
    *,
    fsm: VocabFSM,
) -> tuple[VocabFSM, dict[str, object] | None]:
    state, payload = get_next_payload_toggle(
        conn,
        state=fsm.state,
        cat_live_enabled=_cat_live_enabled(),
    )
    return attach_state(fsm, state), payload


def submit_vocab_choice(
    conn: sqlite3.Connection,
    *,
    fsm: VocabFSM,
    choice_id: int,
) -> tuple[VocabFSM, dict[str, object]]:
    state, result = submit_choice_and_continue_toggle(
        conn,
        state=fsm.state,
        choice_id=choice_id,
        cat_live_enabled=_cat_live_enabled(),
    )
    return attach_state(fsm, state), result
