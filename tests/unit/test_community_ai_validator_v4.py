from __future__ import annotations

from services.community_block.ai_validator import validate_generated_text


def test_validator_accepts_short_single_line_text() -> None:
    out = validate_generated_text("Тут лучше сказать проще и без официоза.", max_chars=220)
    assert out.ok is True
    assert out.cleaned_text == "Тут лучше сказать проще и без официоза."


def test_validator_rejects_bulleted_output() -> None:
    out = validate_generated_text("- первое\n- второе", max_chars=220)
    assert out.ok is False
    assert out.reason == "contains_list"


def test_validator_rejects_multiline_output() -> None:
    out = validate_generated_text("Первая строка.\nВторая строка.", max_chars=220)
    assert out.ok is False
    assert out.reason == "multiline"


def test_validator_rejects_too_long_output() -> None:
    out = validate_generated_text("а" * 221, max_chars=220)
    assert out.ok is False
    assert out.reason == "too_long"
