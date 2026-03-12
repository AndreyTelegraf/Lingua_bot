from __future__ import annotations


def encode_choice_callback(*, choice_id: int) -> str:
    return f"vocab:pick:{choice_id}"


def decode_choice_callback(data: str) -> int:
    parts = data.split(":")

    if len(parts) != 3:
        raise RuntimeError("invalid_callback_format")

    if parts[0] != "vocab" or parts[1] != "pick":
        raise RuntimeError("invalid_callback_prefix")

    try:
        return int(parts[2])
    except ValueError as e:
        raise RuntimeError("invalid_callback_choice_id") from e
