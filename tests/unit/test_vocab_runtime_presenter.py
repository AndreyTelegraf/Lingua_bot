from services.vocab_runtime.presenter import present_finished


def test_present_finished_uses_new_ux() -> None:
    text = present_finished({
        "estimated_vocab_size": 2200,
        "estimated_vocab_band": "1500-2500",
        "estimated_cefr_level": "A2",
        "confidence": 0.32,
    })
    assert "Вы правильно ответили на 0 вопросов из 24." in text
    assert "Ваш пассивный словарный запас находится в диапазоне от 1 500 до 2 500 слов." in text
    assert "Ориентировочно это соответствует уровню A2." in text
    assert "A0 — A1 — A1+ — 🟩 A2 — B1 — B2 — C1 — C1+" in text
    assert "Это типичный результат для этого диапазона." in text
    assert "Выводы этого теста приблизительны, они основаны на частотности слов и точности ваших ответов." in text


def test_present_finished_with_grid() -> None:
    text = present_finished({
        "estimated_vocab_size": 2200,
        "estimated_vocab_band": "1500-2500",
        "estimated_cefr_level": "A2",
        "confidence": 0.32,
        "answers": [
            {"is_correct": True},
            {"is_correct": False},
            {"answer_kind": "dont_know"},
        ],
    })
    assert "Вы правильно ответили на 0 вопросов из 24." in text
    assert "Ваш пассивный словарный запас находится в диапазоне от 1 500 до 2 500 слов." in text
    assert "Ориентировочно это соответствует уровню A2." in text
    assert "A0 — A1 — A1+ — 🟩 A2 — B1 — B2 — C1 — C1+" in text
    assert "Это типичный результат для этого диапазона." in text
    assert "Выводы этого теста приблизительны, они основаны на частотности слов и точности ваших ответов." in text
    assert "🟩🟥🟥" in text
