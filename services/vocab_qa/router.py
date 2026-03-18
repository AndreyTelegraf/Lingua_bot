from __future__ import annotations

from pathlib import Path
from typing import Callable

from services.vocab_qa.ru_gloss_audit import run_noun_audit
from services.vocab_qa.verb_gloss_audit import run_verb_audit
from services.vocab_qa.adjective_gloss_audit import run_adjective_audit
from services.vocab_qa.adverb_gloss_audit import run_adverb_audit

SUPPORTED_POS = ("noun", "verb", "adjective", "adverb")

AuditFn = Callable[[str, str], dict]


def get_audit_runner(pos: str) -> AuditFn:
    if pos == "noun":
        return run_noun_audit
    if pos == "verb":
        return run_verb_audit
    if pos == "adjective":
        return run_adjective_audit
    if pos == "adverb":
        return run_adverb_audit
    raise ValueError(f"Unsupported pos: {pos}")


def reject_csv_name(pos: str) -> str:
    if pos not in SUPPORTED_POS:
        raise ValueError(f"Unsupported pos: {pos}")
    return f"{pos}_ru_gloss_reject_auto.csv"


def review_csv_name(pos: str) -> str:
    if pos not in SUPPORTED_POS:
        raise ValueError(f"Unsupported pos: {pos}")
    return f"{pos}_ru_gloss_review.csv"


def summary_json_name(pos: str) -> str:
    if pos not in SUPPORTED_POS:
        raise ValueError(f"Unsupported pos: {pos}")
    return f"{pos}_ru_gloss_summary.json"


def count_key(pos: str) -> str:
    if pos not in SUPPORTED_POS:
        raise ValueError(f"Unsupported pos: {pos}")
    return f"active_{pos}"


def available_positions() -> tuple[str, ...]:
    return SUPPORTED_POS
