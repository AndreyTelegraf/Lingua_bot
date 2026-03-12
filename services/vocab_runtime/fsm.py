from __future__ import annotations

from dataclasses import dataclass

from services.vocab_runtime.state import VocabSessionState


@dataclass(slots=True)
class VocabFSM:
    state: VocabSessionState


def can_start(fsm: VocabFSM) -> bool:
    return fsm.state.status == 'idle'


def can_answer(fsm: VocabFSM) -> bool:
    return fsm.state.status == 'in_progress' and fsm.state.current_item_id is not None


def can_finish(fsm: VocabFSM) -> bool:
    return fsm.state.status in ('in_progress', 'finished')


def attach_state(fsm: VocabFSM, state: VocabSessionState) -> VocabFSM:
    return VocabFSM(state=state)
