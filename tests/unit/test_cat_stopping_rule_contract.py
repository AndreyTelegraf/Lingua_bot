import pytest

from services.cat_runtime.stopping import should_stop_cat


def test_stop_when_max_questions_reached() -> None:
    d = should_stop_cat(
        questions_answered=24,
        current_se=0.80,
        min_questions=8,
        max_questions=24,
        target_se=0.35,
    )
    assert d.should_stop is True
    assert d.reason == "max_questions_reached"


def test_do_not_stop_before_min_questions_even_if_precision_good() -> None:
    d = should_stop_cat(
        questions_answered=7,
        current_se=0.20,
        min_questions=8,
        max_questions=24,
        target_se=0.35,
    )
    assert d.should_stop is False
    assert d.reason is None


def test_stop_after_min_questions_when_target_precision_reached() -> None:
    d = should_stop_cat(
        questions_answered=10,
        current_se=0.30,
        min_questions=8,
        max_questions=24,
        target_se=0.35,
    )
    assert d.should_stop is True
    assert d.reason == "target_precision_reached"


def test_continue_after_min_questions_when_precision_not_reached() -> None:
    d = should_stop_cat(
        questions_answered=10,
        current_se=0.50,
        min_questions=8,
        max_questions=24,
        target_se=0.35,
    )
    assert d.should_stop is False
    assert d.reason is None


def test_continue_when_se_missing_and_not_at_max() -> None:
    d = should_stop_cat(
        questions_answered=10,
        current_se=None,
        min_questions=8,
        max_questions=24,
        target_se=0.35,
    )
    assert d.should_stop is False
    assert d.reason is None


def test_invalid_min_questions_rejected() -> None:
    with pytest.raises(ValueError, match="min_questions must be >= 1"):
        should_stop_cat(
            questions_answered=1,
            current_se=0.5,
            min_questions=0,
            max_questions=24,
            target_se=0.35,
        )


def test_invalid_max_questions_rejected() -> None:
    with pytest.raises(ValueError, match="max_questions must be >= min_questions"):
        should_stop_cat(
            questions_answered=1,
            current_se=0.5,
            min_questions=10,
            max_questions=9,
            target_se=0.35,
        )


def test_invalid_target_se_rejected() -> None:
    with pytest.raises(ValueError, match="target_se must be > 0"):
        should_stop_cat(
            questions_answered=1,
            current_se=0.5,
            min_questions=8,
            max_questions=24,
            target_se=0.0,
        )
