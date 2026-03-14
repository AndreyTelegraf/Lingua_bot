from services.vocab_runtime.presenter import present_finished, present_question


def test_present_question() -> None:
    assert present_question({"text": "Pergunta"}) == "Pergunta"


def test_present_finished_uses_new_ux() -> None:
    text = present_finished({
        "estimated_vocab_size": 2200,
        "confidence": 0.32,
    })
    assert "Вы правильно ответили на 0 вопросов из 24." in text
    assert "Ваш пассивный словарный запас находится в диапазоне от 1 500 до 2 500 слов." in text
    assert "Ориентировочно это соответствует уровню A2." in text
    assert "A1 — 🟩 A2 — B1 — B2 — C1" in text
    assert "Это типичный результат для этого диапазона." in text
    assert "Оценка результата приблизительная, она основана на частотности слов и ваших ответах." in text


def test_present_finished_with_grid() -> None:
    text = present_finished({
        "estimated_vocab_size": 2200,
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
    assert "A1 — 🟩 A2 — B1 — B2 — C1" in text
    assert "Это типичный результат для этого диапазона." in text
    assert "Оценка результата приблизительная, она основана на частотности слов и ваших ответах." in text
    assert "🟩🟥🟥" in text
