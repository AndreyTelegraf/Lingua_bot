from __future__ import annotations

from handlers import vocab_v2 as mod


class _Store:
    def __init__(self) -> None:
        self.data = {}

    def get(self, *, user_id: int):
        return self.data.get(user_id)

    def set(self, *, user_id: int, fsm) -> None:
        self.data[user_id] = fsm

    def clear(self, *, user_id: int) -> None:
        self.data.pop(user_id, None)


def test_vocab_v2_start_preserves_runtime_native_payload_e2e(monkeypatch) -> None:
    store = _Store()

    monkeypatch.setattr(
        mod,
        "handle_vocab_start",
        lambda **kwargs: {
            "ok": True,
            "text": "Pergunta",
            "keyboard": [{"text": "A", "callback_data": "x"}],
            "finished": False,
            "fsm": {"s": 1},
            "runtime_branch": "cat",
            "cat_native": True,
            "visible_mode": "cat",
            "visible_semantics": "adaptive",
            "runtime_native_payload": {
                "kind": "question",
                "mode": "vocab",
                "session_id": "cat:vocab:u1:a1",
                "status": "in_progress",
                "theta": 0.1,
                "se": 0.4,
                "item_id": 10,
                "prompt_text": "Pergunta nativa",
                "answer_key": "Resposta",
                "stop_reason": None,
                "payload_version": "cat_runtime_payload_v1",
            },
        },
    )

    out = mod.vocab_v2_start(conn="CONN", store=store, user_id=123)

    assert out["runtime_branch"] == "cat"
    assert out["cat_native"] is True
    assert out["e2e_runtime_native"] is True
    assert out["e2e_payload_kind"] == "question"
    assert out["runtime_native_payload"]["kind"] == "question"
    assert store.get(user_id=123) == {"s": 1}


def test_vocab_v2_callback_preserves_runtime_native_payload_e2e(monkeypatch) -> None:
    store = _Store()
    store.set(user_id=123, fsm={"prev": 1})

    monkeypatch.setattr(
        mod,
        "handle_vocab_callback",
        lambda **kwargs: {
            "ok": True,
            "text": "Resultado",
            "keyboard": [],
            "finished": True,
            "fsm": None,
            "runtime_branch": "cat",
            "cat_native": True,
            "visible_mode": "cat",
            "visible_semantics": "adaptive",
            "runtime_native_payload": {
                "kind": "result",
                "mode": "vocab",
                "session_id": "cat:vocab:u1:a1",
                "status": "finished",
                "theta": 0.2,
                "se": 0.3,
                "item_id": None,
                "prompt_text": None,
                "answer_key": None,
                "stop_reason": "target_precision_reached",
                "payload_version": "cat_runtime_payload_v1",
            },
        },
    )

    out = mod.vocab_v2_callback(conn="CONN", store=store, user_id=123, callback_data="vocab:pick:1")

    assert out["runtime_branch"] == "cat"
    assert out["cat_native"] is True
    assert out["e2e_runtime_native"] is True
    assert out["e2e_payload_kind"] == "result"
    assert out["runtime_native_payload"]["kind"] == "result"
    assert store.get(user_id=123) is None


def test_vocab_v2_start_marks_non_native_when_payload_absent(monkeypatch) -> None:
    store = _Store()

    monkeypatch.setattr(
        mod,
        "handle_vocab_start",
        lambda **kwargs: {
            "ok": True,
            "text": "legacy",
            "keyboard": [],
            "finished": False,
            "fsm": {"s": 1},
            "runtime_branch": "legacy",
        },
    )

    out = mod.vocab_v2_start(conn="CONN", store=store, user_id=123)

    assert out["e2e_runtime_native"] is False
    assert out["e2e_payload_kind"] is None
