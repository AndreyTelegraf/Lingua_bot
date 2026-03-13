import os

from services.vocab_runtime.scoring import ScoringInput, score_attempt_default


def test_scoring_selector_default_is_v2(monkeypatch) -> None:
    monkeypatch.delenv("LINGUA_VOCAB_SCORING_MODEL", raising=False)
    out = score_attempt_default(
        ScoringInput(
            attempt_id=1,
            total_questions=1,
            correct_answers=1,
            bin_stats={"1K": 1.0},
            freq_points=[500],
        )
    )
    assert out["scoring_model"] == "runtime_scoring_v2"


def test_scoring_selector_env_can_force_v1(monkeypatch) -> None:
    monkeypatch.setenv("LINGUA_VOCAB_SCORING_MODEL", "runtime_scoring_v1")
    out = score_attempt_default(
        ScoringInput(
            attempt_id=2,
            total_questions=2,
            correct_answers=2,
            bin_stats={"2K": 1.0, "5K": 1.0},
            freq_points=[1100, 2400],
        )
    )
    assert out["scoring_model"] == "runtime_scoring_v1"
