from __future__ import annotations

from bot.common_handlers import vocab_v2 as ui
from handlers import vocab_v2 as hv2
from services.vocab_runtime import handler_layer as hl
from services.cat_runtime import runtime as cr


def test_rollout_readiness_runtime_exposes_native_surface() -> None:
    assert hasattr(cr, "CATRuntimeNativePayload")
    assert hasattr(cr, "CATRuntimeStartResult")
    assert hasattr(cr, "CATRuntimeAnswerResult")
    assert hasattr(cr, "build_cat_runtime_native_payload")
    assert hasattr(cr, "start_cat_session_runtime_native")
    assert hasattr(cr, "answer_cat_session_runtime_native")


def test_rollout_readiness_handler_layer_consumes_runtime_native() -> None:
    assert hasattr(hl, "_runtime_payload_to_handler_fields")
    out = hl._runtime_payload_to_handler_fields(
        type(
            "Payload",
            (),
            {
                "kind": "question",
                "mode": "vocab",
                "session_id": "cat:vocab:u1:a1",
                "status": "in_progress",
                "theta": 0.12,
                "se": 0.44,
                "item_id": 10,
                "prompt_text": "Pergunta final",
                "answer_key": "Resposta",
                "stop_reason": None,
                "payload_version": "cat_runtime_payload_v1",
            },
        )()
    )
    assert out["runtime_branch"] == "cat"
    assert out["cat_native"] is True
    assert out["cat_payload_kind"] == "question"
    assert out["runtime_native_payload"]["prompt_text"] == "Pergunta final"


def test_rollout_readiness_vocab_v2_handler_preserves_e2e_native_chain() -> None:
    out = hv2._attach_e2e_runtime_native_payload(
        {
            "runtime_branch": "cat",
            "cat_native": True,
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
    assert out["runtime_branch"] == "cat"
    assert out["e2e_runtime_native"] is True
    assert out["e2e_payload_kind"] == "result"


def test_rollout_readiness_ui_prefers_native_payload_as_source_of_truth() -> None:
    out = ui._attach_ui_render(
        {
            "ok": True,
            "text": "legacy text should lose",
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
                "prompt_text": "Pergunta rollout readiness",
                "answer_key": "Resposta",
                "stop_reason": None,
                "payload_version": "cat_runtime_payload_v1",
            },
        }
    )
    assert out["visible_mode"] == "cat"
    assert out["cat_native"] is True
    assert out["cat_payload_kind"] == "question"
    assert "Pergunta rollout readiness" in out["text"]


def test_rollout_readiness_final_result_shape_is_cat_native() -> None:
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
    assert out["cat_native"] is True
    assert out["cat_payload_kind"] == "result"
    assert "Причина остановки: target_precision_reached" in out["text"]
