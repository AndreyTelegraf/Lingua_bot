from __future__ import annotations

from bot.common_handlers import vocab_v2 as mod


def test_runtime_native_payload_has_absolute_priority_over_legacy_shape() -> None:
    out = mod._attach_ui_render(
        {
            "ok": True,
            "text": "legacy should lose",
            "keyboard": [{"text": "A", "callback_data": "x"}],
            "runtime_branch": "cat",
            "ui_branch": "cat",
            "cat_native": True,
            "cat_payload_kind": "result",
            "runtime_native_payload": {
                "kind": "question",
                "mode": "vocab",
                "session_id": "cat:vocab:u1:a1",
                "status": "in_progress",
                "theta": 0.12,
                "se": 0.44,
                "item_id": 10,
                "prompt_text": "Pergunta nativa prioritária",
                "answer_key": "Resposta",
                "stop_reason": None,
                "payload_version": "cat_runtime_payload_v1",
            },
        }
    )

    assert out["runtime_branch"] == "cat"
    assert out["cat_native"] is True
    assert out["cat_payload_kind"] == "question"
    assert out["visible_mode"] == "cat"
    assert out["text"].startswith("🎯 Адаптивный вопрос\n\n")
    assert "Pergunta nativa prioritária" in out["text"]
    assert "Причина остановки" not in out["text"]


def test_runtime_native_result_overrides_question_like_legacy_shape() -> None:
    out = mod._attach_ui_render(
        {
            "ok": True,
            "text": "legacy result text",
            "keyboard": [{"text": "A", "callback_data": "x"}],
            "runtime_branch": "cat",
            "ui_branch": "cat",
            "finished": False,
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

    assert out["cat_payload_kind"] == "result"
    assert out["text"].startswith("🎯 Адаптивный результат\n\n")
    assert "Причина остановки: target_precision_reached" in out["text"]


def test_legacy_path_still_works_without_runtime_native_payload() -> None:
    out = mod._attach_ui_render(
        {
            "ok": True,
            "text": "legacy only",
            "keyboard": [{"text": "A", "callback_data": "x"}],
            "runtime_branch": "legacy",
        }
    )

    assert out["runtime_branch"] == "legacy"
    assert out["visible_mode"] == "legacy"
    assert out["cat_native"] is False
    assert out["text"] == "legacy only"
