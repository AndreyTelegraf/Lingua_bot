from __future__ import annotations


def present_finished(payload: dict[str, object]) -> str:
    size = int(payload.get("estimated_vocab_size", 0) or 0)
    lines = [
        f"Ваш пассивный словарный запас составляет около {size} слов.",
        "",
        "Это приблизительная оценка, она основана на частотности слов и ваших ответах.",
    ]

    answers = payload.get("answers")
    if isinstance(answers, list) and answers:
        marks: list[str] = []
        for answer in answers:
            if not isinstance(answer, dict):
                continue
            if answer.get("answer_kind") == "dont_know":
                marks.append("🟨")
            elif bool(answer.get("is_correct", False)):
                marks.append("🟩")
            else:
                marks.append("🟥")
        if marks:
            lines.extend(["", "".join(marks)])

    return "\n".join(lines)


def present_question(view: dict[str, object]) -> str:
    return str(view["text"])
