from __future__ import annotations

from types import SimpleNamespace

from services.vocab_runtime import handler_layer as mod


def _payload(**kwargs):
    base = {
        "kind": "question",
        "mode": "vocab",
        "session_id": "cat:vocab:u1:a1",
        "status": "in_progress",
        "theta": 0.12,
        "se": 0.44,
        "item_id": 10,
        "prompt_text": "Pergunta",
        "answer_key": "Resposta",
        "stop_reason": None,
        "payload_version": "cat_runtime_payload_v1",
    }
    base.update(kwargs)
    return SimpleNamespace(**base)


def test_handle_vocab_start_uses_runtime_native_payload_when_present(monkeypatch) -> None:
    monkeypatch.setattr(
        mod,
        "_handle_vocab_start_base",
        lambda **kwargs: {
            "ok": True,
            "text": "legacy-shaped text",
            "keyboard": [{"text": "A", "callback_data": "x"}],
            "fsm": {"s": 1},
            "finished": False,
            "payload": _payload(kind="question"),
        },
    )

    out = mod.handle_vocab_start(conn="CONN", user_id=123)

    assert out["runtime_branch"] == "cat"
    assert out["cat_native"] is True
    assert out["cat_payload_kind"] == "question"
    assert out["visible_mode"] == "cat"
    assert out["visible_semantics"] == "adaptive"
    assert out["runtime_native_payload"]["kind"] == "question"
    assert out["runtime_native_payload"]["item_id"] == 10
    assert out["runtime_native_payload"]["prompt_text"] == "Pergunta"


def test_handle_vocab_callback_uses_runtime_native_result_payload_when_present(monkeypatch) -> None:
    monkeypatch.setattr(
        mod,
        "_handle_vocab_callback_base",
        lambda **kwargs: {
            "ok": True,
            "text": "finished",
            "keyboard": [],
            "fsm": None,
            "finished": True,
            "payload": _payload(
                kind="result",
                item_id=None,
                prompt_text=None,
                answer_key=None,
                stop_reason="target_precision_reached",
                status="finished",
            ),
        },
    )

    out = mod.handle_vocab_callback(conn="CONN", fsm={"s": 1}, callback_data="vocab:pick:1")

    assert out["runtime_branch"] == "cat"
    assert out["cat_native"] is True
    assert out["cat_payload_kind"] == "result"
    assert out["runtime_native_payload"]["kind"] == "result"
    assert out["runtime_native_payload"]["stop_reason"] == "target_precision_reached"


def test_handle_vocab_start_falls_back_to_legacy_semantics_without_payload(monkeypatch) -> None:
    monkeypatch.setattr(
        mod,
        "_handle_vocab_start_base",
        lambda **kwargs: {
            "ok": True,
            "text": "legacy start",
            "keyboard": [{"text": "A", "callback_data": "x"}],
            "fsm": {"s": 1},
            "finished": False,
        },
    )

    out = mod.handle_vocab_start(conn="CONN", user_id=123)

    assert out["runtime_branch"] == "legacy"
    assert out["cat_native"] is False
    assert out["visible_mode"] == "legacy"
    assert out["runtime_native_payload"] is None


def test_handle_vocab_callback_keeps_non_dict_payload_unchanged(monkeypatch) -> None:
    monkeypatch.setattr(
        mod,
        "_handle_vocab_callback_base",
        lambda **kwargs: "raw-payload",
    )

    out = mod.handle_vocab_callback(conn="CONN", fsm={"s": 1}, callback_data="vocab:pick:1")
    assert out == "raw-payload"
