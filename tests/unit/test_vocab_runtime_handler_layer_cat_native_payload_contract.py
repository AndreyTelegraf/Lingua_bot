from __future__ import annotations

from services.vocab_runtime import handler_layer as mod


def test_handle_vocab_start_marks_cat_question_payload(monkeypatch) -> None:
    monkeypatch.setattr(
        mod,
        "_handle_vocab_start_base",
        lambda **kwargs: {
            "ok": True,
            "text": "next question",
            "keyboard": [{"text": "A", "callback_data": "x"}],
            "finished": False,
            "runtime_branch": "cat",
        },
    )

    out = mod.handle_vocab_start(conn="CONN", user_id=123)

    assert out["runtime_branch"] == "cat"
    assert out["cat_payload_kind"] == "question"
    assert out["cat_native"] is True
    assert out["visible_mode"] == "cat"
    assert out["visible_semantics"] == "adaptive"


def test_handle_vocab_callback_marks_cat_result_payload(monkeypatch) -> None:
    monkeypatch.setattr(
        mod,
        "_handle_vocab_callback_base",
        lambda **kwargs: {
            "ok": True,
            "text": "finished",
            "keyboard": [],
            "finished": True,
            "runtime_branch": "cat",
        },
    )

    out = mod.handle_vocab_callback(conn="CONN", fsm={"s": 1}, callback_data="vocab:pick:1")

    assert out["runtime_branch"] == "cat"
    assert out["cat_payload_kind"] == "result"
    assert out["cat_native"] is True
    assert out["visible_mode"] == "cat"
    assert out["visible_semantics"] == "adaptive"


def test_handle_vocab_start_keeps_legacy_payload(monkeypatch) -> None:
    monkeypatch.setattr(
        mod,
        "_handle_vocab_start_base",
        lambda **kwargs: {
            "ok": True,
            "text": "legacy start",
            "keyboard": [{"text": "A", "callback_data": "x"}],
            "finished": False,
        },
    )

    out = mod.handle_vocab_start(conn="CONN", user_id=123)

    assert out["runtime_branch"] == "legacy"
    assert out["cat_payload_kind"] is None
    assert out["cat_native"] is False
    assert out["visible_mode"] == "legacy"
    assert out["visible_semantics"] == "static"


def test_handle_vocab_callback_keeps_non_dict_payload_unchanged(monkeypatch) -> None:
    monkeypatch.setattr(
        mod,
        "_handle_vocab_callback_base",
        lambda **kwargs: "raw-payload",
    )

    out = mod.handle_vocab_callback(conn="CONN", fsm={"s": 1}, callback_data="vocab:pick:1")
    assert out == "raw-payload"
