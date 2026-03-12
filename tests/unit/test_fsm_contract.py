from domain.attempts.fsm import can_transition
from domain.shared.enums import AttemptStatus


def test_happy_path_transitions() -> None:
    assert can_transition(AttemptStatus.IDLE, AttemptStatus.SELECTING)
    assert can_transition(AttemptStatus.SELECTING, AttemptStatus.QUESTION_READY)
    assert can_transition(AttemptStatus.SELECTING, AttemptStatus.FINISHING)
    assert can_transition(AttemptStatus.QUESTION_READY, AttemptStatus.AWAITING_ANSWER)
    assert can_transition(AttemptStatus.AWAITING_ANSWER, AttemptStatus.PROCESSING_ANSWER)
    assert can_transition(AttemptStatus.PROCESSING_ANSWER, AttemptStatus.SELECTING)
    assert can_transition(AttemptStatus.PROCESSING_ANSWER, AttemptStatus.FINISHING)
    assert can_transition(AttemptStatus.FINISHING, AttemptStatus.FINISHED)


def test_abort_path_transitions() -> None:
    assert can_transition(AttemptStatus.SELECTING, AttemptStatus.ABORTING)
    assert can_transition(AttemptStatus.QUESTION_READY, AttemptStatus.ABORTING)
    assert can_transition(AttemptStatus.AWAITING_ANSWER, AttemptStatus.ABORTING)
    assert can_transition(AttemptStatus.PROCESSING_ANSWER, AttemptStatus.ABORTING)
    assert can_transition(AttemptStatus.ABORTING, AttemptStatus.ABORTED)


def test_illegal_transition() -> None:
    assert not can_transition(AttemptStatus.IDLE, AttemptStatus.FINISHED)
    assert not can_transition(AttemptStatus.FINISHED, AttemptStatus.SELECTING)
    assert not can_transition(AttemptStatus.ABORTED, AttemptStatus.SELECTING)
