from enum import StrEnum


class ModeCode(StrEnum):
    VOCAB = "vocab"
    LEVEL = "level"
    CIPLE = "ciple"


class AttemptStatus(StrEnum):
    IDLE = "idle"
    SELECTING = "selecting"
    QUESTION_READY = "question_ready"
    AWAITING_ANSWER = "awaiting_answer"
    PROCESSING_ANSWER = "processing_answer"
    FINISHING = "finishing"
    FINISHED = "finished"
    ABORTING = "aborting"
    ABORTED = "aborted"


TERMINAL_STATUSES: set[AttemptStatus] = {
    AttemptStatus.FINISHED,
    AttemptStatus.ABORTED,
}
