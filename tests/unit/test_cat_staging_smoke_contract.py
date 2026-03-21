from __future__ import annotations

from bot.common_handlers import vocab_v2 as ui
from handlers import vocab_v2 as hv2
from services.vocab_runtime import handler_layer as hl


def test_ui_module_exposes_runtime_native_render_path() -> None:
    assert hasattr(ui, "_runtime_native_payload")
    assert hasattr(ui, "_apply_runtime_native_payload")
    assert hasattr(ui, "_attach_ui_render")


def test_handler_module_preserves_e2e_runtime_native_markers() -> None:
    assert hasattr(hv2, "_attach_e2e_runtime_native_payload")
    out = hv2._attach_e2e_runtime_native_payload(
        {
            "runtime_native_payload": {
                "kind": "question",
                "mode": "vocab",
                "session_id": "cat:vocab:u1:a1",
                "status": "in_progress",
                "theta": 0.1,
                "se": 0.4,
                "item_id": 10,
                "prompt_text": "Pergunta",
                "answer_key": "Resposta",
                "stop_reason": None,
                "payload_version": "cat_runtime_payload_v1",
            },
            "runtime_branch": "cat",
            "cat_native": True,
        }
    )
    assert out["e2e_runtime_native"] is True
    assert out["e2e_payload_kind"] == "question"


def test_handler_layer_runtime_native_fields_are_present() -> None:
    out = hl._runtime_payload_to_handler_fields(
        type(
            "Payload",
            (),
            {
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
        )()
    )
    assert out["runtime_branch"] == "cat"
    assert out["cat_native"] is True
    assert out["cat_payload_kind"] == "result"
    assert out["runtime_native_payload"]["stop_reason"] == "target_precision_reached"


def test_ui_strictly_prefers_runtime_native_payload_in_smoke_shape() -> None:
    out = ui._attach_ui_render(
        {
            "ok": True,
            "text": "legacy fallback text",
            "keyboard": [{"text": "A", "callback_data": "x"}],
            "runtime_branch": "cat",
            "ui_branch": "cat",
            "runtime_native_payload": {
                "kind": "question",
                "mode": "vocab",
                "session_id": "cat:vocab:u1:a1",
                "status": "in_progress",
                "theta": 0.1,
                "se": 0.4,
                "item_id": 10,
                "prompt_text": "Pergunta staging smoke",
                "answer_key": "Resposta",
                "stop_reason": None,
                "payload_version": "cat_runtime_payload_v1",
            },
        }
    )
    assert out["visible_mode"] == "cat"
    assert out["cat_native"] is True
    assert out["cat_payload_kind"] == "question"
    assert "Pergunta staging smoke" in out["text"]


def test_ui_result_smoke_shape_uses_native_stop_reason() -> None:
    out = ui._attach_ui_render(
        {
            "ok": True,
            "text": "resultado base",
            "keyboard": [],
            "runtime_branch": "cat",
            "ui_branch": "cat",
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
        }
    )
    assert out["visible_mode"] == "cat"
    assert out["cat_payload_kind"] == "result"
    assert "Причина остановки: target_precision_reached" in out["text"]
