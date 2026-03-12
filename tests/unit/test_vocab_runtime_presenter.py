from services.vocab_runtime.presenter import present_finished, present_question


def test_present_question() -> None:
    assert present_question({"text": "Pergunta"}) == "Pergunta"


def test_present_finished_uses_new_ux() -> None:
    assert present_finished({
        "estimated_vocab_size": 2200,
        "confidence": 0.32,
    }) == "Ваш пассивный словарный запас составляет около 2200 слов.\n\nЭто приблизительная оценка, она основана на частотности слов и ваших ответах."


def test_present_finished_with_grid() -> None:
    assert present_finished({
        "estimated_vocab_size": 2200,
        "confidence": 0.32,
        "answers": [
            {"is_correct": True},
            {"is_correct": False},
            {"answer_kind": "dont_know"},
        ],
    }) == "Ваш пассивный словарный запас составляет около 2200 слов.\n\nЭто приблизительная оценка, она основана на частотности слов и ваших ответах.\n\n🟩🟥🟨"
