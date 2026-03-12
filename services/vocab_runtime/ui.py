from __future__ import annotations


def build_choice_keyboard(payload: dict[str, object]) -> list[dict[str, object]]:
    choices = payload.get("choices")
    if not isinstance(choices, list) or len(choices) != 6:
        raise RuntimeError("invalid_choices_payload")

    out: list[dict[str, object]] = []
    for row in choices:
        if not isinstance(row, dict):
            raise RuntimeError("invalid_choice_row")
        out.append(
            {
                "text": str(row["choice_text"]),
                "choice_id": int(row["choice_id"]),
                "position_index": int(row["position_index"]),
            }
        )
    return out
