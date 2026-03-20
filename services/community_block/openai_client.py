from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from openai import OpenAI

from app.config import get_settings


@dataclass(slots=True)
class OpenAIGenerationResult:
    provider: str
    model: str
    output_text: str
    response_id: str | None
    raw: dict[str, Any]


def _extract_output_text(response: Any) -> str:
    text = getattr(response, "output_text", None)
    if isinstance(text, str) and text.strip():
        return text.strip()

    parts: list[str] = []
    output = getattr(response, "output", None) or []
    for item in output:
        content = getattr(item, "content", None) or []
        for chunk in content:
            chunk_text = getattr(chunk, "text", None)
            if isinstance(chunk_text, str) and chunk_text.strip():
                parts.append(chunk_text.strip())
    return "\n".join(parts).strip()


def build_openai_client() -> OpenAI:
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is empty")
    return OpenAI(
        api_key=settings.openai_api_key,
        timeout=float(settings.community_ai_timeout_seconds),
    )


def generate_reply(*, system_prompt: str, developer_prompt: str, user_prompt: str, model: str | None = None) -> OpenAIGenerationResult:
    settings = get_settings()
    client = build_openai_client()
    chosen_model = str(model or settings.community_ai_model or "gpt-5").strip()

    response = client.responses.create(
        model=chosen_model,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "developer", "content": developer_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )

    output_text = _extract_output_text(response)
    response_id = getattr(response, "id", None)

    try:
        raw = response.model_dump()
    except Exception:
        raw = {
            "id": response_id,
            "output_text": output_text,
        }

    return OpenAIGenerationResult(
        provider="openai",
        model=chosen_model,
        output_text=output_text,
        response_id=response_id,
        raw=raw,
    )
