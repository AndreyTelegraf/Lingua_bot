from modes.vocab.router import _result_text


def test_result_text_passes_previous_result_block_to_presenter():
    text = _result_text(
        estimated_vocab_band="2500-4000",
        estimated_vocab_size=3200,
        confidence=0.8,
        correct_answers=17,
        total_answers=24,
        previous_correct_answers=12,
        previous_total_questions=24,
        previous_estimated_vocab_band="1500-2500",
        previous_estimated_vocab_size=1800,
    )

    assert "Ваш прошлый тест:" in text
    assert "В предыдущей попытке вы правильно ответили на 12 вопросов из 24, запас был от 1 500 до 2 500 слов." in text
