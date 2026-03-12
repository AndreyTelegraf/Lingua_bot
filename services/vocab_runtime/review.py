from __future__ import annotations

def render_review(answers: list[dict]) -> str:
    lines = ["Разбор ответов:", ""]
    for i, a in enumerate(answers, start=1):
        if a.get("answer_kind") == "dont_know":
            mark = "🟨"; status = "Не знаю"
        elif a.get("is_correct"):
            mark = "🟩"; status = "Правильно"
        else:
            mark = "🟥"; status = "Неправильно"
        word = a.get("word") or "?"
        lines.append(f"{i}. {mark} {word} — {status}")
    return "\n".join(lines)
