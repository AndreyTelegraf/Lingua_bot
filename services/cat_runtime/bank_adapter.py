from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Any

from .item_model import CATItemModel


@dataclass(slots=True)
class CATBankAdapterStats:
    total_rows: int
    mapped_rows: int
    skipped_rows: int


def _clean_str(value: Any) -> str:
    return str(value or "").strip()


def _coerce_float(value: Any, *, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _coerce_bool(value: Any, *, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    raw = str(value).strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    return default


def map_vocab_row_to_cat_item(
    row: Mapping[str, Any],
    *,
    default_mode: str = "vocab",
    default_modality: str = "mcq",
) -> CATItemModel:
    item_id = int(row["id"])
    lemma = _clean_str(row.get("lemma"))
    question_text = _clean_str(row.get("question_text"))
    correct_answer = _clean_str(row.get("correct_answer"))

    prompt_text = question_text or lemma
    answer_key = correct_answer

    if prompt_text == "":
        raise ValueError("prompt_text cannot be empty")
    if answer_key == "":
        raise ValueError("answer_key cannot be empty")

    freq_rank = row.get("freq_rank")
    difficulty_b = _coerce_float(row.get("difficulty_b"), default=0.0)
    if "difficulty_b" not in row:
        if freq_rank is not None:
            try:
                fr = float(freq_rank)
                if fr <= 1000:
                    difficulty_b = -1.5
                elif fr <= 2000:
                    difficulty_b = -0.8
                elif fr <= 5000:
                    difficulty_b = 0.0
                elif fr <= 10000:
                    difficulty_b = 0.8
                else:
                    difficulty_b = 1.5
            except (TypeError, ValueError):
                difficulty_b = 0.0

    discrimination_a = _coerce_float(row.get("discrimination_a"), default=1.0)
    guessing_c = _coerce_float(row.get("guessing_c"), default=0.2 if default_modality == "mcq" else 0.0)
    upper_d = _coerce_float(row.get("upper_d"), default=0.95)

    bin_name = _clean_str(row.get("bin_name")).upper() or None
    cefr_target = _clean_str(row.get("level")).upper() or None
    content_tag = _clean_str(row.get("topic_tag")) or None
    skill_tag = _clean_str(row.get("pos")) or None

    return CATItemModel(
        item_id=item_id,
        mode=_clean_str(row.get("mode")) or default_mode,
        modality=_clean_str(row.get("modality")) or default_modality,
        prompt_text=prompt_text,
        answer_key=answer_key,
        difficulty_b=difficulty_b,
        discrimination_a=discrimination_a,
        guessing_c=guessing_c,
        upper_d=upper_d,
        cefr_target=cefr_target,
        content_tag=content_tag or bin_name,
        skill_tag=skill_tag,
        is_active=_coerce_bool(row.get("is_active"), default=True),
        exposure_max_rate=None,
    )


def map_vocab_rows_to_cat_items(
    rows: Iterable[Mapping[str, Any]],
    *,
    default_mode: str = "vocab",
    default_modality: str = "mcq",
    active_only: bool = True,
) -> list[CATItemModel]:
    out: list[CATItemModel] = []
    for row in rows:
        if active_only and not _coerce_bool(row.get("is_active"), default=True):
            continue
        out.append(
            map_vocab_row_to_cat_item(
                row,
                default_mode=default_mode,
                default_modality=default_modality,
            )
        )
    return out


def summarize_vocab_rows_adapter(
    rows: Iterable[Mapping[str, Any]],
    *,
    active_only: bool = True,
) -> CATBankAdapterStats:
    total = 0
    mapped = 0
    skipped = 0
    for row in rows:
        total += 1
        if active_only and not _coerce_bool(row.get("is_active"), default=True):
            skipped += 1
            continue
        mapped += 1
    return CATBankAdapterStats(
        total_rows=total,
        mapped_rows=mapped,
        skipped_rows=skipped,
    )
