from services.vocab_runtime.telegram_adapter import build_telegram_question_view


def test_build_telegram_question_view_happy_path() -> None:
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

    view = build_telegram_question_view(payload)
    assert view['text'] == 'casa'
    assert view['item_id'] == 1
    assert view['attempt_id'] == 777
    assert len(view['keyboard']) == 6
    assert view['keyboard'][0]['text'] == 'дом'
    assert view['keyboard'][0]['callback_data'] == 'vocab:pick:101'
