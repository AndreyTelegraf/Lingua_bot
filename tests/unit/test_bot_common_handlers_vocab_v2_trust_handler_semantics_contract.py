from __future__ import annotations

from bot.common_handlers import vocab_v2 as mod


class _Store:
    def __init__(self) -> None:
        self.data = {}

    def get(self, *, user_id: int):
        return self.data.get(user_id)

    def set(self, *, user_id: int, fsm) -> None:
        self.data[user_id] = fsm

    def clear(self, *, user_id: int) -> None:
        self.data.pop(user_id, None)


def test_attach_ui_render_trusts_handler_cat_question_semantics() -> None:
    out = mod._attach_ui_render({
        "ok": True,
        "text": "next question",
        "keyboard": [{"text": "A", "callback_data": "x"}],
        "runtime_branch": "cat",
        "visible_mode": "cat",
        "visible_semantics": "adaptive",
        "cat_payload_kind": "question",
        "cat_native": True,
    })

    assert out["ui_branch"] == "cat"
    assert out["visible_mode"] == "cat"
    assert out["cat_payload_kind"] == "question"
    assert out["cat_native"] is True
    assert out["text"].startswith("🎯 Адаптивный вопрос\n\n")


def test_attach_ui_render_trusts_handler_cat_result_semantics() -> None:
    out = mod._attach_ui_render({
        "ok": True,
        "text": "finished",
        "keyboard": [],
        "runtime_branch": "cat",
        "visible_mode": "cat",
        "visible_semantics": "adaptive",
        "cat_payload_kind": "result",
        "cat_native": True,
    })

    assert out["ui_branch"] == "cat"
    assert out["cat_payload_kind"] == "result"
    assert out["text"].startswith("🎯 Адаптивный результат\n\n")


def test_attach_ui_render_keeps_legacy_when_handler_marks_legacy() -> None:
    out = mod._attach_ui_render({
        "ok": True,
        "text": "legacy",
        "keyboard": [{"text": "A", "callback_data": "x"}],
        "runtime_branch": "legacy",
        "visible_mode": "legacy",
        "visible_semantics": "static",
        "cat_payload_kind": None,
        "cat_native": False,
    })

    assert out["ui_branch"] == "legacy"
    assert out["visible_mode"] == "legacy"
    assert out["cat_native"] is False
    assert out["text"] == "legacy"


def test_run_vocab_v2_start_ui_uses_handler_native_semantics(monkeypatch) -> None:
    monkeypatch.setattr(
        mod,
        "run_vocab_v2_start",
        lambda **kwargs: {
            "ok": True,
            "text": "started",
            "keyboard": [{"text": "A", "callback_data": "x"}],
            "finished": False,
            "runtime_branch": "cat",
            "visible_mode": "cat",
            "visible_semantics": "adaptive",
            "cat_payload_kind": "question",
            "cat_native": True,
        },
    )

    out = mod.run_vocab_v2_start_ui(conn="CONN", store=_Store(), user_id=123)

    assert out["ui_branch"] == "cat"
    assert out["cat_payload_kind"] == "question"
    assert out["cat_native"] is True
