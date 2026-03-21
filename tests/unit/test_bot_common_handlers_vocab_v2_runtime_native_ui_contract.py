from __future__ import annotations

from bot.common_handlers import vocab_v2 as mod


def test_attach_ui_render_uses_runtime_native_question_payload() -> None:
    out = mod._attach_ui_render(
        {
            "ok": True,
            "text": "legacy text should not win",
            "keyboard": [{"text": "A", "callback_data": "x"}],
            "runtime_branch": "cat",
            "ui_branch": "cat",
            "runtime_native_payload": {
                "kind": "question",
                "mode": "vocab",
                "session_id": "cat:vocab:u1:a1",
                "status": "in_progress",
                "theta": 0.12,
                "se": 0.44,
                "item_id": 10,
                "prompt_text": "Pergunta nativa",
                "answer_key": "Resposta",
                "stop_reason": None,
                "payload_version": "cat_runtime_payload_v1",
            },
        }
    )

    assert out["visible_mode"] == "cat"
    assert out["visible_semantics"] == "adaptive"
    assert out["cat_native"] is True
    assert out["cat_payload_kind"] == "question"
    assert out["text"].startswith("🎯 Адаптивный вопрос\n\n")
    assert "Pergunta nativa" in out["text"]


def test_attach_ui_render_uses_runtime_native_result_payload() -> None:
    out = mod._attach_ui_render(
        {
            "ok": True,
            "text": "legacy result",
            "keyboard": [],
            "runtime_branch": "cat",
            "ui_branch": "cat",
            "runtime_native_payload": {
                "kind": "result",
                "mode": "vocab",
                "session_id": "cat:vocab:u1:a1",
                "status": "finished",
                "theta": 0.12,
                "se": 0.31,
                "item_id": None,
                "prompt_text": None,
                "answer_key": None,
                "stop_reason": "target_precision_reached",
                "payload_version": "cat_runtime_payload_v1",
            },
        }
    )

    assert out["visible_mode"] == "cat"
    assert out["cat_payload_kind"] == "result"
    assert out["text"].startswith("🎯 Адаптивный результат\n\n")
    assert "Причина остановки: target_precision_reached" in out["text"]


def test_attach_ui_render_falls_back_without_runtime_native_payload() -> None:
    out = mod._attach_ui_render(
        {
            "ok": True,
            "text": "legacy-shaped cat payload",
            "keyboard": [{"text": "A", "callback_data": "x"}],
            "runtime_branch": "cat",
        }
    )

    assert out["visible_mode"] == "cat"
    assert out["cat_native"] is True
    assert out["text"]
