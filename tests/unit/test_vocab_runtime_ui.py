from services.vocab_runtime.ui import build_choice_keyboard


def test_build_choice_keyboard_happy_path() -> None:
    payload = {
        'attempt_id': 777,
        'item_id': 1,
        'lemma': 'casa',
        'question_text': 'casa',
        'pos': 'noun',
        'choices': [
            {'choice_id': 101, 'choice_text': 'дом', 'position_index': 1},
            {'choice_id': 102, 'choice_text': 'окно', 'position_index': 2},
            {'choice_id': 103, 'choice_text': 'книга', 'position_index': 3},
            {'choice_id': 104, 'choice_text': 'вода', 'position_index': 4},
            {'choice_id': 105, 'choice_text': 'стол', 'position_index': 5},
            {'choice_id': 106, 'choice_text': 'дорога', 'position_index': 6},
        ],
    }

    keyboard = build_choice_keyboard(payload)
    assert len(keyboard) == 6
    assert keyboard[0]['text'] == 'дом'
    assert keyboard[0]['choice_id'] == 101
    assert [x['position_index'] for x in keyboard] == [1, 2, 3, 4, 5, 6]


def test_build_choice_keyboard_rejects_invalid_payload() -> None:
    try:
        build_choice_keyboard({'choices': [{'choice_id': 1}]})
        assert False, 'expected RuntimeError'
    except RuntimeError as e:
        assert str(e) == 'invalid_choices_payload'
