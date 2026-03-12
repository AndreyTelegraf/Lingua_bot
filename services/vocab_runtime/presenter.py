from __future__ import annotations

def _emoji(answer: dict) -> str:
    if answer.get("answer_kind") == "dont_know":
        return "🟨"
    if answer.get("is_correct"):
        return "🟩"
    return "🟥"

def _answers_grid(payload: dict) -> str:
    answers = payload.get("answers") or []
    if not answers:
        return ""
    return "".join(_emoji(a) for a in answers)

def _confidence_text(conf: float) -> str:
    pct = round(float(conf) * 100)
    return f"{pct}% — статистическая уверенность оценки (зависит от числа ответов)"

def present_finished(payload: dict[str, object]) -> str:
    size = payload.get("estimated_vocab_size")
    conf = payload.get("confidence")
    lines: list[str] = []
    if size is not None:
        lines.append(f"Пассивный словарный запас: ≈ {int(size)} слов")
    if conf is not None:
        lines.append(f"Уверенность оценки: {_confidence_text(float(conf))}")
    grid = _answers_grid(payload)
    if grid:
        lines.append("")
        lines.append(grid)
    return "\n".join(lines)

def present_question(view: dict[str, object]) -> str:
    return str(view["text"])
