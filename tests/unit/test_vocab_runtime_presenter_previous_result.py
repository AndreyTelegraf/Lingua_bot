from services.vocab_runtime.presenter import present_finished


def test_present_finished_shows_previous_result_block_when_available():
    text = present_finished({
        "correct_answers": 17,
        "total_questions": 24,
        "estimated_vocab_size": 3200,
        "estimated_vocab_band": "2.5k-4k",
        "confidence": 0.8,
        "previous_correct_answers": 12,
        "previous_total_questions": 24,
        "previous_estimated_vocab_band": "1.5k-2.5k",
        "previous_estimated_vocab_size": 1800,
    })

    assert "Ваш прошлый результат:" in text
    assert "12/24 правильных ответов и оценка запаса в 1 500–2 500 слов." in text
