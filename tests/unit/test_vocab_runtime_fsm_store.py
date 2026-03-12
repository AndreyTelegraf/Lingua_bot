from services.vocab_runtime.fsm import VocabFSM
from services.vocab_runtime.fsm_store import InMemoryVocabFSMStore
from services.vocab_runtime.state import VocabSessionState


def test_fsm_store_happy_path() -> None:
    store = InMemoryVocabFSMStore()
    fsm = VocabFSM(state=VocabSessionState(user_id=42, attempt_id=100, current_item_id=1, status="in_progress"))

    assert store.get(user_id=42) is None

    store.set(user_id=42, fsm=fsm)
    assert store.get(user_id=42) is fsm

    store.clear(user_id=42)
    assert store.get(user_id=42) is None
