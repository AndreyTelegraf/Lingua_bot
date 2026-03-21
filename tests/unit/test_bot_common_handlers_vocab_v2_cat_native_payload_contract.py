from __future__ import annotations

from bot.common_handlers import vocab_v2 as mod


def test_attach_ui_render_keeps_legacy_payload_non_cat() -> None:
    out = mod._attach_ui_render({
        "ok": True,
        "text": "started",
        "keyboard": [{"text": "A", "callback_data": "x"}],
        "runtime_branch": "legacy",
    })

    assert out["ui_branch"] == "legacy"
    assert out["visible_mode"] == "legacy"
    assert out["visible_semantics"] == "static"
    assert out["cat_payload_kind"] is None
    assert out["cat_native"] is False
    assert out["text"] == "started"


def test_attach_ui_render_builds_cat_question_payload() -> None:
    out = mod._attach_ui_render({
        "ok": True,
        "text": "next question",
        "keyboard": [{"text": "A", "callback_data": "x"}],
        "finished": False,
        "runtime_branch": "cat",
    })

    assert out["ui_branch"] == "cat"
    assert out["visible_mode"] == "cat"
    assert out["visible_semantics"] == "adaptive"
    assert out["cat_payload_kind"] == "question"
    assert out["cat_native"] is True
    assert out["text"].startswith("🎯 Адаптивный вопрос\n\n")
    assert "Следующий вопрос подбирается по вашим ответам." in out["text"]
    assert out["keyboard"][0]["callback_data"] == "vocab:cat:info"
    assert out["keyboard"][1]["callback_data"] == "x"


def test_attach_ui_render_builds_cat_result_payload() -> None:
    out = mod._attach_ui_render({
        "ok": True,
        "text": "finished",
        "keyboard": [],
        "finished": True,
        "runtime_branch": "cat",
    })

    assert out["visible_mode"] == "cat"
    assert out["cat_payload_kind"] == "result"
    assert out["cat_native"] is True
    assert out["text"].startswith("🎯 Адаптивный результат\n\n")


def test_cat_info_payload_is_cat_native_message() -> None:
    out = mod._cat_info_payload()

    assert out["ui_branch"] == "cat"
    assert out["visible_mode"] == "cat"
    assert out["visible_semantics"] == "adaptive"
    assert out["cat_payload_kind"] == "message"
    assert out["cat_native"] is True
