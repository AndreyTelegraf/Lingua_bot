from __future__ import annotations

from bot.common_handlers import vocab_v2 as mod


def test_attach_ui_render_keeps_legacy_visible_payload() -> None:
    out = mod._attach_ui_render({
        "ok": True,
        "text": "started",
        "keyboard": [{"text": "A", "callback_data": "x"}],
        "runtime_branch": "legacy",
    })

    assert out["ui_branch"] == "legacy"
    assert out["visible_mode"] == "legacy"
    assert out["visible_semantics"] == "static"
    assert out["text"] == "started"
    assert out["keyboard"] == [{"text": "A", "callback_data": "x"}]


def test_attach_ui_render_builds_cat_visible_payload() -> None:
    out = mod._attach_ui_render({
        "ok": True,
        "text": "next question",
        "keyboard": [{"text": "A", "callback_data": "x"}],
        "runtime_branch": "cat",
    })

    assert out["ui_branch"] == "cat"
    assert out["visible_mode"] == "cat"
    assert out["visible_semantics"] == "adaptive"
    assert out["text"].startswith("🎯 CAT\n\n")
    assert out["keyboard"][0]["callback_data"] == "vocab:cat:info"
    assert out["keyboard"][1]["callback_data"] == "x"


def test_attach_ui_render_builds_cat_keyboard_when_missing() -> None:
    out = mod._attach_ui_render({
        "ok": True,
        "text": "next question",
        "runtime_branch": "cat",
    })

    assert out["visible_mode"] == "cat"
    assert isinstance(out["keyboard"], list)
    assert out["keyboard"][0]["callback_data"] == "vocab:cat:info"


def test_cat_info_payload_is_explicitly_adaptive() -> None:
    out = mod._cat_info_payload()

    assert out["ui_branch"] == "cat"
    assert out["visible_mode"] == "cat"
    assert out["visible_semantics"] == "adaptive"
    assert "адаптивном режиме" in out["text"]
