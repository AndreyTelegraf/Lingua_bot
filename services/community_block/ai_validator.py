from __future__ import annotations

from dataclasses import dataclass
import re


BULLET_RE = re.compile(r"(?m)^\s*([-•*]|\d+\.)\s+")
MULTI_NEWLINE_RE = re.compile(r"\n{2,}")
SPACE_RE = re.compile(r"[ \t]+")


@dataclass(slots=True)
class ValidationResult:
    ok: bool
    cleaned_text: str
    reason: str


def normalize_generated_text(text: str) -> str:
    s = str(text or "").replace("\r", "\n").strip()
    s = MULTI_NEWLINE_RE.sub("\n", s)
    s = "\n".join(SPACE_RE.sub(" ", line).strip() for line in s.split("\n"))
    s = "\n".join(line for line in s.split("\n") if line)
    return s.strip()


def validate_generated_text(text: str, *, max_chars: int = 220) -> ValidationResult:
    cleaned = normalize_generated_text(text)
    if not cleaned:
        return ValidationResult(False, cleaned, "empty")
    if BULLET_RE.search(cleaned):
        return ValidationResult(False, cleaned, "contains_list")
    if "\n" in cleaned:
        return ValidationResult(False, cleaned, "multiline")
    if len(cleaned) > max_chars:
        return ValidationResult(False, cleaned, "too_long")
    if cleaned.count("?") > 1:
        return ValidationResult(False, cleaned, "too_many_questions")
    return ValidationResult(True, cleaned, "ok")
