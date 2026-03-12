from services.vocab_runtime.review import render_review


def test_render_review_compact_lines() -> None:
    out = render_review(
        [
            {
                "word": "insistir",
                "is_correct": False,
                "answer_kind": "answered",
                "correct_answer": "настаивать",
            },
            {
                "word": "dia",
                "is_correct": True,
                "answer_kind": "answered",
                "correct_answer": "день",
            },
            {
                "word": "depressa",
                "is_correct": False,
                "answer_kind": "dont_know",
                "correct_answer": "быстро",
            },
            {
                "word": "fraude",
                "is_correct": False,
                "answer_kind": "report_error",
                "correct_answer": "мошенничество",
            },
        ]
    )

    assert out == (
        "Разбор ответов:\n\n"
        '🟥 1. insistir — правильно "настаивать"\n'
        "🟩 2. dia — правильно\n"
        '🟥 3. depressa — правильно "быстро"\n'
        "🟨 4. fraude — сообщить об ошибке"
    )
