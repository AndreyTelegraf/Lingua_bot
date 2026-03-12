from services.vocab_runtime.presenter import present_finished, present_question


def test_present_question() -> None:
    assert present_question({'text': 'casa'}) == 'casa'


def test_present_finished() -> None:
    assert present_finished({'total_questions': 2, 'correct_answers': 1}) == 'Vocab finished. Score: 1/2'
