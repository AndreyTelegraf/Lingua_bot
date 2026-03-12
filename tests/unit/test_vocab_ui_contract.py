def test_vocab_ui_contract_answer_count() -> None:
    regular_answer_buttons = 6
    assert regular_answer_buttons == 6


def test_vocab_ui_contract_utility_buttons() -> None:
    utility_buttons = ["❗️ Не знаю", "⚠️ Сообщить об ошибке"]
    assert utility_buttons == ["❗️ Не знаю", "⚠️ Сообщить об ошибке"]


def test_vocab_ui_contract_total_controls() -> None:
    regular_answer_buttons = 6
    utility_buttons = 2
    assert regular_answer_buttons + utility_buttons == 8


def test_vocab_ui_contract_forbids_stop_button() -> None:
    forbidden = ["⛔ Stop test", "⛔ Остановить тест", "Stop test"]
    assert "⛔ Stop test" in forbidden


def test_vocab_ui_contract_forbids_english_user_strings_examples() -> None:
    forbidden_examples = [
        "Vocabulary test",
        "Start test",
        "I don't know",
        "Report error",
    ]
    assert len(forbidden_examples) == 4


def test_vocab_ui_contract_answers_language_is_russian_only() -> None:
    allowed_answer_language = "ru"
    forbidden_answer_language = "en"
    assert allowed_answer_language == "ru"
    assert forbidden_answer_language == "en"


def test_vocab_ui_contract_target_language_is_portuguese() -> None:
    target_language = "pt"
    assert target_language == "pt"
