from services.vocab_runtime.state import (
    VocabSessionState,
    clear_current_question,
    finish_session,
    set_current_question,
    start_session,
)


def test_state_happy_path() -> None:
    state = start_session(user_id=42, attempt_id=100)
    assert isinstance(state, VocabSessionState)
    assert state.user_id == 42
    assert state.attempt_id == 100
    assert state.current_item_id is None
    assert state.status == "in_progress"

    state2 = set_current_question(state, item_id=555)
    assert state2.current_item_id == 555
    assert state2.status == "in_progress"

    state3 = clear_current_question(state2)
    assert state3.current_item_id is None
    assert state3.status == "in_progress"

    state4 = finish_session(state3)
    assert state4.current_item_id is None
    assert state4.status == "finished"
