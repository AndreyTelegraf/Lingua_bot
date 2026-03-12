from __future__ import annotations

from services.vocab_runtime.fsm import VocabFSM


class InMemoryVocabFSMStore:
    def __init__(self) -> None:
        self._data: dict[int, VocabFSM] = {}

    def get(self, *, user_id: int) -> VocabFSM | None:
        return self._data.get(user_id)

    def set(self, *, user_id: int, fsm: VocabFSM) -> None:
        self._data[user_id] = fsm

    def clear(self, *, user_id: int) -> None:
        self._data.pop(user_id, None)
