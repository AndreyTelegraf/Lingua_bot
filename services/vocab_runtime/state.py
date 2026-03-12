from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class VocabSessionState:
    user_id: int
    attempt_id: int | None = None
    current_item_id: int | None = None
    status: str = "idle"


def start_session(*, user_id: int, attempt_id: int) -> VocabSessionState:
    return VocabSessionState(user_id=user_id, attempt_id=attempt_id, current_item_id=None, status="in_progress")


def set_current_question(state: VocabSessionState, *, item_id: int) -> VocabSessionState:
    return VocabSessionState(
        user_id=state.user_id,
        attempt_id=state.attempt_id,
        current_item_id=item_id,
        status=state.status,
    )


def clear_current_question(state: VocabSessionState) -> VocabSessionState:
    return VocabSessionState(
        user_id=state.user_id,
        attempt_id=state.attempt_id,
        current_item_id=None,
        status=state.status,
    )


def finish_session(state: VocabSessionState) -> VocabSessionState:
    return VocabSessionState(
        user_id=state.user_id,
        attempt_id=state.attempt_id,
        current_item_id=None,
        status="finished",
    )
