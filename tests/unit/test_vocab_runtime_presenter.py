from services.vocab_runtime.presenter import present_finished, present_question


def test_present_question() -> None:
    assert present_question({"text": "Pergunta"}) == "Pergunta"


def test_present_finished_uses_new_ux() -> None:
    assert present_finished({
        "estimated_vocab_size": 2200,
        "confidence": 0.32,
    }) == "Пассивный словарный запас: ≈ 2200 слов\nУверенность оценки: 32% — статистическая уверенность оценки (зависит от числа ответов)"


def test_present_finished_with_grid() -> None:
    assert present_finished({
        "estimated_vocab_size": 2200,
        "confidence": 0.32,
        "answers": [
            {"is_correct": True},
            {"is_correct": False},
            {"answer_kind": "dont_know"},
        ],
    }) == "Пассивный словарный запас: ≈ 2200 слов\nУверенность оценки: 32% — статистическая уверенность оценки (зависит от числа ответов)\n\n🟩🟥🟨"
