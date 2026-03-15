from modes.vocab.router import _result_text


def test_router_result_text_delegates_to_presenter():
    text = _result_text(
        estimated_vocab_band="1500-2500",
        estimated_vocab_size=1800,
        confidence=0.8,
        correct_answers=17,
        total_answers=24,
    )

    assert "Вы правильно ответили на 17 вопросов из 24." in text
    assert "Ваш пассивный словарный запас составляет 1 500–2 500 слов." in text.replace("\u2060", "")
    assert "Это уровень выше среднего для понимания португальского языка." in text
    assert "A0  A1  A1+  A2  B1  B2  C1  C1+" not in text
