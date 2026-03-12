from services.vocab_runtime.presenter import present_finished, present_question


def test_present_question() -> None:
    assert present_question({"text": "casa"}) == "casa"


def test_present_finished_prefers_summary_text() -> None:
    assert present_finished(
        {
            "summary_text": "Vocab finished. Score: 1/2 (50%)\nEstimated vocabulary: ~2400 words\nBand: 1.5k-2.5k\nConfidence: 27%"
        }
    ) == "Vocab finished. Score: 1/2 (50%)\nEstimated vocabulary: ~2400 words\nBand: 1.5k-2.5k\nConfidence: 27%"


def test_present_finished_fallback() -> None:
    assert present_finished(
        {
            "total_questions": 2,
            "correct_answers": 1,
            "accuracy_pct": 50.0,
            "estimated_vocab_size": 2400,
            "estimated_vocab_band": "1.5k-2.5k",
            "confidence": 0.27,
        }
    ) == "Vocab finished. Score: 1/2 (50%)\nEstimated vocabulary: ~2400 words\nBand: 1.5k-2.5k\nConfidence: 27%"
