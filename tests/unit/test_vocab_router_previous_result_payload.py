from modes.vocab.router import _result_text


def test_result_text_passes_previous_result_block_to_presenter():
    text = _result_text(
        estimated_vocab_band="2.5k-4k",
        estimated_vocab_size=3200,
        confidence=0.8,
        correct_answers=17,
        total_answers=24,
        previous_correct_answers=12,
        previous_total_questions=24,
        previous_estimated_vocab_band="1.5k-2.5k",
        previous_estimated_vocab_size=1800,
    )

    assert "Ваш прошлый результат:" in text
    assert "12/24 правильных ответов и оценка запаса в 1 500–2 500 слов." in text
