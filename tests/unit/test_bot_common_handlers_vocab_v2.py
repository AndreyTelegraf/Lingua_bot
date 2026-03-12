from bot.common_handlers.vocab_v2 import _keyboard


def test_keyboard_builder() -> None:
    kb = _keyboard([
        {"text": "дом", "callback_data": "vocab:pick:101"},
        {"text": "окно", "callback_data": "vocab:pick:102"},
    ])

    assert len(kb.inline_keyboard) == 2
    assert kb.inline_keyboard[0][0].text == "дом"
    assert kb.inline_keyboard[0][0].callback_data == "vocab:pick:101"
    assert kb.inline_keyboard[1][0].text == "окно"
    assert kb.inline_keyboard[1][0].callback_data == "vocab:pick:102"
