from services.vocab_runtime.presenter import present_finished


def test_present_finished_shows_previous_result_block_when_available():
    text = present_finished({
        "correct_answers": 17,
        "total_questions": 24,
        "estimated_vocab_size": 3200,
        "estimated_vocab_band": "2500-4000",
        "confidence": 0.8,
        "previous_correct_answers": 12,
        "previous_total_questions": 24,
        "previous_estimated_vocab_band": "1500-2500",
        "previous_estimated_vocab_size": 1800,
    })

    assert "Ваш прошлый тест:" in text
    assert "В прошлой попытке вы правильно ответили на 12 вопросов из 24, запас был от 1 500 до 2 500 слов." in text
