from __future__ import annotations

from dataclasses import dataclass
from typing import Any


CAT_VALID_CEFR = {"A1", "A2", "B1", "B2", "C1", "C2"}
CAT_VALID_MODALITIES = {"mcq", "gap_fill", "cloze", "reading", "listening"}


@dataclass(slots=True)
class CATItemModel:
    item_id: int
    mode: str
    modality: str
    prompt_text: str
    answer_key: str
    difficulty_b: float
    discrimination_a: float = 1.0
    guessing_c: float = 0.0
    upper_d: float = 1.0
    cefr_target: str | None = None
    content_tag: str | None = None
    skill_tag: str | None = None
    is_active: bool = True
    exposure_max_rate: float | None = None


def _clean_str(value: Any) -> str:
    return str(value or "").strip()


def validate_cat_item_model(item: CATItemModel) -> list[str]:
    errors: list[str] = []

    if int(item.item_id) <= 0:
        errors.append("item_id must be positive")

    if _clean_str(item.mode) == "":
        errors.append("mode must be non-empty")

    modality = _clean_str(item.modality)
    if modality == "":
        errors.append("modality must be non-empty")
    elif modality not in CAT_VALID_MODALITIES:
        errors.append(f"unsupported modality: {modality}")

    if _clean_str(item.prompt_text) == "":
        errors.append("prompt_text must be non-empty")

    if _clean_str(item.answer_key) == "":
        errors.append("answer_key must be non-empty")

    a = float(item.discrimination_a)
    b = float(item.difficulty_b)
    c = float(item.guessing_c)
    d = float(item.upper_d)

    if a <= 0:
        errors.append("discrimination_a must be > 0")

    if b < -6.0 or b > 6.0:
        errors.append("difficulty_b must be within [-6, 6]")

    if c < 0.0 or c >= 1.0:
        errors.append("guessing_c must be within [0, 1)")

    if d <= 0.0 or d > 1.0:
        errors.append("upper_d must be within (0, 1]")

    if c >= d:
        errors.append("guessing_c must be less than upper_d")

    cefr = item.cefr_target
    if cefr is not None:
        cefr = _clean_str(cefr).upper()
        if cefr not in CAT_VALID_CEFR:
            errors.append(f"unsupported cefr_target: {item.cefr_target}")

    rate = item.exposure_max_rate
    if rate is not None:
        rate = float(rate)
        if rate <= 0.0 or rate > 1.0:
            errors.append("exposure_max_rate must be within (0, 1]")

    return errors
