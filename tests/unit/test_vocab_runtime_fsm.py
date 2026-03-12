from services.vocab_runtime.fsm import VocabFSM, attach_state, can_answer, can_finish, can_start
from services.vocab_runtime.state import VocabSessionState


def test_fsm_contract() -> None:
    idle = VocabFSM(state=VocabSessionState(user_id=42, attempt_id=None, current_item_id=None, status='idle'))
    assert can_start(idle) is True
    assert can_answer(idle) is False
    assert can_finish(idle) is False

    in_progress = attach_state(
        idle,
        VocabSessionState(user_id=42, attempt_id=100, current_item_id=555, status='in_progress'),
    )
    assert can_start(in_progress) is False
    assert can_answer(in_progress) is True
    assert can_finish(in_progress) is True

    finished = attach_state(
        in_progress,
        VocabSessionState(user_id=42, attempt_id=100, current_item_id=None, status='finished'),
    )
    assert can_start(finished) is False
    assert can_answer(finished) is False
    assert can_finish(finished) is True
