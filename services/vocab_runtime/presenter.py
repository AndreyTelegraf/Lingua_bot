from __future__ import annotations


def _band_to_range_text(band: str, size: int) -> str:
    if band in {"<1.5k", "1.5k-2.5k", "2.5k-4k", "4k-6k", "6k-8k", "8k+"}:
        mapping = {
            "<1.5k": "до 1 500 слов",
            "1.5k-2.5k": "от 1 500 до 2 500 слов",
            "2.5k-4k": "от 2 500 до 4 000 слов",
            "4k-6k": "от 4 000 до 6 000 слов",
            "6k-8k": "от 6 000 до 8 000 слов",
            "8k+": "8 000+ слов",
        }
        return mapping[band]

    if size <= 0:
        return "недостаточно данных"
    if size < 1500:
        return "до 1 500 слов"
    if size < 2500:
        return "от 1 500 до 2 500 слов"
    if size < 4000:
        return "от 2 500 до 4 000 слов"
    if size < 6000:
        return "от 4 000 до 6 000 слов"
    if size < 8000:
        return "от 6 000 до 8 000 слов"
    return "8 000+ слов"


def present_finished(payload: dict[str, object]) -> str:
    size = int(payload.get("estimated_vocab_size", 0) or 0)
    band = str(payload.get("estimated_vocab_band") or "")
    range_text = _band_to_range_text(band, size)

    lines = [
        f"Ваш пассивный словарный запас находится в диапазоне {range_text}.",
        "",
        "Это приблизительная оценка, она основана на частотности слов и ваших ответах.",
    ]

    answers = payload.get("answers")
    if isinstance(answers, list) and answers:
        marks: list[str] = []
        for answer in answers:
            if not isinstance(answer, dict):
                continue
            if bool(answer.get("is_correct", False)):
                marks.append("🟩")
            else:
                marks.append("🟥")
        if marks:
            lines.extend(["", "".join(marks)])

    return "\n".join(lines)


def present_question(view: dict[str, object]) -> str:
    return str(view["text"])
