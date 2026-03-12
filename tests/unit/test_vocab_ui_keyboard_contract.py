from modes.vocab.router import _question_keyboard


def test_question_keyboard_order_matches_frozen_contract() -> None:
    kb = _question_keyboard(
        [
            {"choice_id": 101, "choice_text": "вариант 1", "position_index": 1},
            {"choice_id": 102, "choice_text": "вариант 2", "position_index": 2},
            {"choice_id": 103, "choice_text": "вариант 3", "position_index": 3},
            {"choice_id": 104, "choice_text": "вариант 4", "position_index": 4},
            {"choice_id": 105, "choice_text": "вариант 5", "position_index": 5},
            {"choice_id": 106, "choice_text": "вариант 6", "position_index": 6},
        ],
        "cb-token",
    )

    rows = kb.inline_keyboard
    assert len(rows) == 8

    assert rows[0][0].text == "❗️ Не знаю"
    assert rows[1][0].text == "вариант 1"
    assert rows[2][0].text == "вариант 2"
    assert rows[3][0].text == "вариант 3"
    assert rows[4][0].text == "вариант 4"
    assert rows[5][0].text == "вариант 5"
    assert rows[6][0].text == "вариант 6"
    assert rows[7][0].text == "⚠️ Сообщить об ошибке"
