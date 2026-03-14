from services.vocab_runtime.presenter import present_finished


def test_present_finished_adds_cefr_scale_and_fallback_peer_text():
    payload = {
        "correct_answers": 17,
        "total_questions": 24,
        "estimated_vocab_size": 1800,
        "estimated_vocab_band": "1.5k-2.5k",
        "confidence": 0.78,
    }

    text = present_finished(payload)

    assert "Ориентировочно это соответствует уровню A2." in text
    assert "A1 — 🟩 A2 — B1 — B2 — C1" in text
    assert "Это типичный результат для этого диапазона." in text


def test_present_finished_uses_explicit_peer_comparison_text_when_present():
    payload = {
        "correct_answers": 20,
        "total_questions": 24,
        "estimated_vocab_size": 3200,
        "estimated_vocab_band": "2.5k-4k",
        "estimated_cefr_level": "B1",
        "peer_comparison_text": "Это типичный результат для уровня B1.",
        "confidence": 0.82,
    }

    text = present_finished(payload)

    assert "Ориентировочно это соответствует уровню B1." in text
    assert "A1 — A2 — 🟩 B1 — B2 — C1" in text
    assert "Это типичный результат для уровня B1." in text
