from __future__ import annotations


def _band_to_range_bounds(band: str, size: int) -> tuple[int | None, int | None]:
    mapping = {
        "<500": (0, 500),
        "500-1000": (500, 1000),
        "1000-1500": (1000, 1500),
        "1500-2500": (1500, 2500),
        "2500-4000": (2500, 4000),
        "4000-6000": (4000, 6000),
        "6000-8000": (6000, 8000),
        "8k+": (8000, None),

        "<1.5k": (0, 1500),
        "1.5k-2.5k": (1500, 2500),
        "2.5k-4k": (2500, 4000),
        "4k-6k": (4000, 6000),
        "6k-8k": (6000, 8000),
    }
    if band in mapping:
        return mapping[band]

    if size <= 0:
        return (None, None)
    if size < 1500:
        return (0, 1500)
    if size < 2500:
        return (1500, 2500)
    if size < 4000:
        return (2500, 4000)
    if size < 6000:
        return (4000, 6000)
    if size < 8000:
        return (6000, 8000)
    return (8000, None)


def _fmt_num(n: int) -> str:
    return f"{n:,}".replace(",", " ")




def _ru_plural_question(n: int) -> str:
    return _ru_plural_form(n, "вопрос", "вопроса", "вопросов")


def _normalize_range_text(text: str) -> str:
    text = str(text).strip()

    replacements = {
        "до 500 слов": "<500 слов",
        "до 500": "<500",
        "от 8 000 слов": "8000+ слов",
        "от 8 000": "8000+",
        "от 8000 слов": "8000+ слов",
        "от 8000": "8000+",
    }

    return replacements.get(text, text)


def _ru_plural_form(n: int, one: str, few: str, many: str) -> str:
    n = abs(int(n))
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not (12 <= n % 100 <= 14):
        return few
    return many


def _ru_plural_question(n: int) -> str:
    return _ru_plural_form(n, "вопрос", "вопроса", "вопросов")


def _ru_plural_answer(n: int) -> str:
    return _ru_plural_form(n, "ответ", "ответа", "ответов")


def _band_to_range_text(band: str, size: int) -> str:
    low, high = _band_to_range_bounds(band, size)

    if low is None and high is None:
        return "недостаточно данных"
    if low in (None, 0):
        return f"до {_fmt_num(int(high or 1500))} слов"
    if high is None:
        return f"от {_fmt_num(int(low))} слов"
    return f"от {_fmt_num(int(low))} до {_fmt_num(int(high))} слов"


def present_finished(payload: dict[str, object]) -> str:
    size = int(payload.get("estimated_vocab_size", 0) or 0)
    band = str(payload.get("estimated_vocab_band") or "")

    correct = int(payload.get("correct_answers", 0))
    total = int(payload.get("total_questions", 24) or 24)
    if total <= 0:
        total = 24

    lines = [
        f"Вы правильно ответили на {correct} {_ru_plural_question(correct)} из {total}.",
        "",
        f"Ваш пассивный словарный запас находится в диапазоне {_normalize_range_text(_band_to_range_text(band, size))}.",
        "",
        "Выводы этого теста приблизительны, они основаны на частотности слов и точности ваших ответов.",
    ]

    answers = payload.get("answers")
    if isinstance(answers, list) and answers:
        marks: list[str] = []
        for answer in answers:
            if not isinstance(answer, dict):
                continue
            marks.append("🟩" if bool(answer.get("is_correct", False)) else "🟥")
        if marks:
            lines.extend(["", "".join(marks)])

    return _add_previous_test_separator("\n".join(lines))


def present_question(view: dict[str, object]) -> str:
    return str(view["text"])

# === VOCAB RESULT CEFR EXTENSION ===


_ORIGINAL_PRESENT_FINISHED = present_finished


def _as_int(value: object | None) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _display_band(value: object | None) -> str:
    raw = str(value or "").strip()
    wj = "\u2060"
    mapping = {
        "<500": "<500",
        "500-1000": f"500{wj}–{wj}1 000",
        "1000-1500": f"1 000{wj}–{wj}1 500",
        "1500-2500": f"1 500{wj}–{wj}2 500",
        "2500-4000": f"2 500{wj}–{wj}4 000",
        "4000-6000": f"4 000{wj}–{wj}6 000",
        "6000-8000": f"6 000{wj}–{wj}8 000",
        "8000+": f"8 000{wj}+",
        "8k+": f"8 000{wj}+",
        "<1.5k": f"1 000{wj}–{wj}1 500",
        "1.5k-2.5k": f"1 500{wj}–{wj}2 500",
        "2.5k-4k": f"2 500{wj}–{wj}4 000",
        "4k-6k": f"4 000{wj}–{wj}6 000",
        "6k-8k": f"6 000{wj}–{wj}8 000",
    }
    return mapping.get(raw, raw)


def _cefr_label_from_correct_answers(correct_answers: int) -> str:
    if correct_answers <= 2:
        return "A0"
    if correct_answers <= 5:
        return "A1"
    if correct_answers <= 8:
        return "A1+"
    if correct_answers <= 11:
        return "A2"
    if correct_answers <= 14:
        return "B1"
    if correct_answers <= 18:
        return "B2"
    if correct_answers <= 21:
        return "C1"
    return "C1+"


def _level_description_from_label(label: str) -> str:
    descriptions = {
        "A0": "Это нулевой уровень понимания португальского языка. Знакомые слова иногда узнаются на слух, но связную речь пока понять почти невозможно.",
        "A1": "Это начальный уровень понимания португальского языка. Понятны отдельные слова и очень простые фразы, особенно в знакомых бытовых ситуациях.",
        "A1+": "Это базовый уровень понимания португальского языка. Простая повседневная речь начинает складываться в смысл, если говорят медленно и на знакомые темы.",
        "A2": "Это элементарный уровень понимания португальского языка. Основной смысл коротких фраз и диалогов уже улавливается, особенно в обычных бытовых разговорах.",
        "B1": "Это средний уровень понимания португальского языка. В целом понятна основная мысль разговоров и простых текстов на повседневные темы.",
        "B2": "Это уровень выше среднего для понимания португальского языка. Большинство разговоров и обсуждений уже воспринимаются без особых усилий.",
        "C1": "Это продвинутый уровень понимания португальского языка. Сложная речь и абстрактные темы обычно понятны, даже если разговор идёт быстро.",
        "C1+": "Это очень высокий уровень понимания португальского языка. Почти любые разговоры, фильмы и тексты воспринимаются естественно и без напряжения.",
    }
    return descriptions.get(label, descriptions["C1+"])




def _previous_result_block(payload: dict[str, object]) -> list[str]:
    previous_band = _display_band(payload.get("previous_estimated_vocab_band"))
    previous_correct = _as_int(payload.get("previous_correct_answers"))
    previous_total = _as_int(payload.get("previous_total_questions"))

    if not previous_band or previous_correct is None or previous_total is None:
        return []

    return [
        "Ваш предыдущий результат",
        f"{previous_band} слов ({previous_correct}/{previous_total})",
    ]


def present_finished(payload: dict[str, object]) -> str:
    correct = _as_int(payload.get("correct_answers")) or 0
    total = _as_int(payload.get("total_answers"))
    if total is None:
        total = _as_int(payload.get("total_questions")) or 24
    if total <= 0:
        total = 24

    band = _display_band(payload.get("estimated_vocab_band"))
    level = _cefr_label_from_correct_answers(correct)
    description = _level_description_from_label(level)
    previous_block = _previous_result_block(payload)

    parts = [
        f"Вы правильно ответили на {correct} {_ru_plural_question(correct)} из {total}.",
        f"Ваш пассивный словарный запас составляет {band} слов.",
        description,
    ]

    if previous_block:
        parts.append("────────────")
        parts.append(previous_block[0] + "\n" + previous_block[1])

    parts.append("Оценка приблизительная и основана\nна частотности слов.")

    return "\n\n".join(parts)
