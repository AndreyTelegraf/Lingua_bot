from __future__ import annotations

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
        "text": str(payload["question_text"]),
        "item_id": int(payload["item_id"]),
        "attempt_id": int(payload["attempt_id"]),
        "keyboard": keyboard_rows,
    }
