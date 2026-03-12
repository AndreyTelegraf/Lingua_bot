from services.vocab_runtime.presenter import present_finished, present_question


def test_present_question() -> None:
    assert present_question({"text": "casa"}) == "casa"


def test_present_finished_prefers_summary_text() -> None:
    assert present_finished({"summary_text": "Vocab finished. Score: 1/2 (50%)"}) == "Vocab finished. Score: 1/2 (50%)"


def test_present_finished_fallback() -> None:
    assert present_finished({"total_questions": 2, "correct_answers": 1, "accuracy_pct": 50.0}) == "Vocab finished. Score: 1/2 (50%)"
