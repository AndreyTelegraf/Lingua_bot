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


def test_attach_ui_render_prefixes_cat_text() -> None:
    out = mod._attach_ui_render({
        "ok": True,
        "text": "started",
        "keyboard": [],
        "runtime_branch": "cat",
    })
    assert out["ui_branch"] == "cat"
    assert out["text"].startswith("🎯 CAT\n\n")
    assert out["text"].endswith("started")


def test_attach_ui_render_keeps_legacy_text_plain() -> None:
    out = mod._attach_ui_render({
        "ok": True,
        "text": "started",
        "keyboard": [],
        "runtime_branch": "legacy",
    })
    assert out["ui_branch"] == "legacy"
    assert out["text"] == "started"


def test_run_vocab_v2_start_ui_renders_cat_branch(monkeypatch) -> None:
    monkeypatch.setattr(
        mod,
        "run_vocab_v2_start",
        lambda **kwargs: {
            "ok": True,
            "text": "started",
            "keyboard": [],
            "finished": False,
            "runtime_branch": "cat",
        },
    )

    out = mod.run_vocab_v2_start_ui(conn="CONN", store=_Store(), user_id=123)

    assert out["runtime_branch"] == "cat"
    assert out["ui_branch"] == "cat"
    assert out["text"].startswith("🎯 CAT\n\n")


def test_run_vocab_v2_callback_ui_renders_legacy_branch(monkeypatch) -> None:
    monkeypatch.setattr(
        mod,
        "run_vocab_v2_callback",
        lambda **kwargs: {
            "ok": True,
            "text": "next",
            "keyboard": [],
            "finished": False,
            "runtime_branch": "legacy",
        },
    )

    out = mod.run_vocab_v2_callback_ui(
        conn="CONN",
        store=_Store(),
        user_id=123,
        callback_data="vocab:pick:1",
    )

    assert out["runtime_branch"] == "legacy"
    assert out["ui_branch"] == "legacy"
    assert out["text"] == "next"
