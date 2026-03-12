from __future__ import annotations


def render_review(answers: list[dict]) -> str:
    lines = ["Разбор ответов:", ""]

    for i, a in enumerate(answers, start=1):
        answer_kind = a.get("answer_kind")
        is_correct = bool(a.get("is_correct"))
        word = str(a.get("word") or "?")
        correct = str(a.get("correct_answer") or "?")

        if answer_kind == "report_error":
            lines.append(f"🟨 {i}. {word} — сообщить об ошибке")
        elif is_correct:
            lines.append(f"🟩 {i}. {word} — правильно")
        else:
            lines.append(f'🟥 {i}. {word} — правильно "{correct}"')

    return "\n".join(lines)
