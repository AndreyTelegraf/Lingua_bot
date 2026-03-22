from __future__ import annotations


def _cat_passthrough_fields(payload: dict[str, object]) -> dict[str, object]:
    out: dict[str, object] = {}
    for key in (
        "cat_route",
        "runtime_branch",
        "runtime_native_payload",
        "cat_native",
        "visible_mode",
        "visible_semantics",
        "cat_payload_kind",
        "e2e_runtime_native",
        "e2e_payload_kind",
    ):
        if key in payload:
            out[key] = payload[key]

    if "cat_route" in payload and "runtime_branch" not in out:
        out["runtime_branch"] = "cat"
    if "cat_route" in payload and "cat_native" not in out:
        out["cat_native"] = True
    if "cat_route" in payload and "visible_mode" not in out:
        out["visible_mode"] = "cat"
    if "cat_route" in payload and "visible_semantics" not in out:
        out["visible_semantics"] = "adaptive"

    return out


from services.vocab_runtime.callbacks import encode_choice_callback
from services.vocab_runtime.ui import build_choice_keyboard


def build_telegram_question_view(payload: dict[str, object]) -> dict[str, object]:
    keyboard_rows = []
    for row in build_choice_keyboard(payload):
        keyboard_rows.append(
            {
                "text": row["text"],
                "callback_data": encode_choice_callback(choice_id=int(row["choice_id"])),
                "position_index": int(row["position_index"]),
            }
        )

    return {
        **_cat_passthrough_fields(payload),
        "text": str(payload["question_text"]),
        "item_id": int(payload["item_id"]),
        "attempt_id": int(payload["attempt_id"]),
        "keyboard": keyboard_rows,
    }
