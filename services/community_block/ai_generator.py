from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .openai_client import generate_reply


@dataclass(slots=True)
class GeneratedReply:
    provider: str
    model: str
    text: str
    response_id: str | None
    raw: dict[str, Any]


def generate_from_prompt_payload(prompt_payload: dict, *, model: str | None = None) -> GeneratedReply:
    result = generate_reply(
        system_prompt=str(prompt_payload["system_prompt"]),
        developer_prompt=str(prompt_payload["developer_prompt"]),
        user_prompt=str(prompt_payload["user_prompt"]),
        model=model,
    )
    return GeneratedReply(
        provider=result.provider,
        model=result.model,
        text=result.output_text,
        response_id=result.response_id,
        raw=result.raw,
    )
