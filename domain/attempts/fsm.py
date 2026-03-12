from dataclasses import dataclass

from domain.shared.enums import AttemptStatus, ModeCode


@dataclass(slots=True)
class RuntimeState:
    mode: ModeCode
    user_id: int
    run_id: int
    status: AttemptStatus
    current_step: int
    current_item_id: str | None
    expected_callback_token: str | None
    expected_message_id: int | None
    revision: int


ALLOWED_TRANSITIONS: dict[AttemptStatus, set[AttemptStatus]] = {
    AttemptStatus.IDLE: {AttemptStatus.SELECTING},
    AttemptStatus.SELECTING: {
        AttemptStatus.QUESTION_READY,
        AttemptStatus.FINISHING,
        AttemptStatus.ABORTING,
    },
    AttemptStatus.QUESTION_READY: {
        AttemptStatus.AWAITING_ANSWER,
        AttemptStatus.ABORTING,
    },
    AttemptStatus.AWAITING_ANSWER: {
        AttemptStatus.PROCESSING_ANSWER,
        AttemptStatus.ABORTING,
    },
    AttemptStatus.PROCESSING_ANSWER: {
        AttemptStatus.SELECTING,
        AttemptStatus.FINISHING,
        AttemptStatus.ABORTING,
    },
    AttemptStatus.FINISHING: {
        AttemptStatus.FINISHED,
    },
    AttemptStatus.FINISHED: set(),
    AttemptStatus.ABORTING: {
        AttemptStatus.ABORTED,
    },
    AttemptStatus.ABORTED: set(),
}


def can_transition(current: AttemptStatus, target: AttemptStatus) -> bool:
    return target in ALLOWED_TRANSITIONS[current]


def require_transition(current: AttemptStatus, target: AttemptStatus) -> None:
    if not can_transition(current, target):
        raise ValueError(f"illegal_fsm_transition: {current} -> {target}")
