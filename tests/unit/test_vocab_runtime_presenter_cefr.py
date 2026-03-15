from services.vocab_runtime.presenter import present_finished


def test_present_finished_adds_cefr_scale_and_fallback_peer_text():
    payload = {
        "correct_answers": 17,
        "total_questions": 24,
        "estimated_vocab_size": 5000,
        "estimated_vocab_band": "4000-6000",
        "confidence": 0.78,
    }

    text = present_finished(payload)

    assert "Ориентировочно это соответствует уровню B2." in text
    assert "A0 A1 A1+ A2 B1 [B2] C1 C1+" in text
    assert "Это типичный результат для этого диапазона." in text


def test_present_finished_uses_explicit_peer_comparison_text_when_present():
    payload = {
        "correct_answers": 23,
        "total_questions": 24,
        "estimated_vocab_size": 9000,
        "estimated_vocab_band": "8k+",
        "estimated_cefr_level": "C1+",
        "peer_comparison_text": "Это типичный результат для уровня C1+.",
        "confidence": 0.82,
    }

    text = present_finished(payload)

    assert "Ориентировочно это соответствует уровню C1+." in text
    assert "A0 A1 A1+ A2 B1 B2 C1 [C1+]" in text
    assert "Это типичный результат для уровня C1+." in text


def test_present_finished_uses_conservative_cefr_cap_for_24q_low_score():
    payload = {
        "correct_answers": 5,
        "total_questions": 24,
        "estimated_vocab_size": 750,
        "estimated_vocab_band": "500-1000",
        "confidence": 0.52,
    }

    text = present_finished(payload)

    assert "Ваш пассивный словарный запас находится в диапазоне от 500 до 1 000 слов." in text
    assert "Ориентировочно это соответствует уровню A1." in text
    assert "A0 [A1] A1+ A2 B1 B2 C1 C1+" in text


def test_present_finished_shows_a0_for_near_zero_score():
    payload = {
        "correct_answers": 2,
        "total_questions": 24,
        "estimated_vocab_size": 300,
        "estimated_vocab_band": "<500",
        "confidence": 0.50,
    }

    text = present_finished(payload)

    assert "Ваш пассивный словарный запас находится в диапазоне <500 слов." in text
    assert "Ориентировочно это соответствует уровню A0." in text
    assert "[A0] A1 A1+ A2 B1 B2 C1 C1+" in text


def test_present_finished_shows_a1plus_honestly():
    payload = {
        "correct_answers": 7,
        "total_questions": 24,
        "estimated_vocab_size": 1250,
        "estimated_vocab_band": "1000-1500",
        "confidence": 0.55,
    }

    text = present_finished(payload)

    assert "Ваш пассивный словарный запас находится в диапазоне от 1 000 до 1 500 слов." in text
    assert "Ориентировочно это соответствует уровню A1+." in text
    assert "A0 A1 [A1+] A2 B1 B2 C1 C1+" in text
