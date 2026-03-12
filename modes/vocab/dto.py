from dataclasses import dataclass


@dataclass(slots=True)
class VocabStartResult:
    mode_run_id: int
    vocab_attempt_id: int
    current_step: int
    status: str


@dataclass(slots=True)
class VocabAbortResult:
    mode_run_id: int
    vocab_attempt_id: int
    status: str
    completion_reason: str


@dataclass(slots=True)
class VocabQuestion:
    mode_run_id: int
    vocab_attempt_id: int
    step_index: int
    item_id: int
    question_text: str
    choices: list[dict[str, object]]
    callback_token: str
    question_limit: int


@dataclass(slots=True)
class VocabFinishResult:
    mode_run_id: int
    vocab_attempt_id: int
    status: str
    completion_reason: str
    estimated_vocab_band: str
    estimated_vocab_size: int
    confidence: float
    correct_answers: int
    total_answers: int


@dataclass(slots=True)
class VocabSubmitAnswerResult:
    mode_run_id: int
    vocab_attempt_id: int
    step_index: int
    item_id: int
    selected_choice_id: int
    is_correct: bool
    selected_choice_text: str
    correct_answer_text: str
    next_status: str
    is_finished: bool
    finish_result: VocabFinishResult | None


@dataclass(slots=True)
class VocabSubmitDontKnowResult:
    mode_run_id: int
    vocab_attempt_id: int
    step_index: int
    item_id: int
    answer_kind: str
    next_status: str
    is_finished: bool
    finish_result: VocabFinishResult | None


@dataclass(slots=True)
class VocabReportErrorResult:
    mode_run_id: int
    vocab_attempt_id: int
    step_index: int
    item_id: int
    action: str
    next_status: str
    is_finished: bool
    finish_result: VocabFinishResult | None


@dataclass(slots=True)
class VocabResult:
    estimated_vocab_band: str | None
    estimated_vocab_size: int | None
    confidence: float | None
    completion_reason: str | None
