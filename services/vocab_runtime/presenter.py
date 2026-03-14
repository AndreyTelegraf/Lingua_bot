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
    n = abs(int(n))
    if n % 10 == 1 and n % 100 != 11:
        return "вопрос"
    if 2 <= n % 10 <= 4 and not (12 <= n % 100 <= 14):
        return "вопроса"
    return "вопросов"


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

import re as _re_vocab_cefr


_ORIGINAL_PRESENT_FINISHED = present_finished


def _estimate_cefr_from_correct_answers(*, correct_answers: int | None, total_questions: int | None) -> str | None:
    if correct_answers is None or total_questions is None:
        return None

    total = int(total_questions or 0)
    if total < 24:
        return None

    c = int(correct_answers or 0)
    if c <= 2:
        return "A0"
    if c <= 5:
        return "A1"
    if c <= 8:
        return "A1+"
    if c <= 11:
        return "A2"
    if c <= 15:
        return "B1"
    if c <= 18:
        return "B2"
    if c <= 21:
        return "C1"
    return "C1+"


def _normalize_cefr_for_scale(level: str | None) -> str | None:
    raw = (level or "").upper()
    return raw or None


def _extract_vocab_size_for_cefr(payload: dict[str, object]) -> int | None:
    raw_size = payload.get("estimated_vocab_size")
    if raw_size is not None:
        try:
            return int(raw_size)
        except (TypeError, ValueError):
            pass

    band = str(payload.get("estimated_vocab_band") or "").strip().lower()
    if not band:
        return None

    band = band.replace(" ", "")
    nums = _re_vocab_cefr.findall(r"\d+(?:\.\d+)?", band)
    if not nums:
        return None

    values: list[int] = []
    for n in nums:
        try:
            values.append(int(float(n) * 1000) if "k" in band else int(float(n)))
        except ValueError:
            continue

    if not values:
        return None

    if "+" in band:
        return values[0]
    if len(values) >= 2:
        return (values[0] + values[1]) // 2
    return values[0]


def _estimate_cefr_level_from_payload(payload: dict[str, object]) -> str | None:
    explicit = str(payload.get("estimated_cefr_level") or "").strip().upper()
    if explicit in {"A0", "A1", "A1+", "A2", "B1", "B2", "C1", "C1+"}:
        return explicit

    by_correct = _estimate_cefr_from_correct_answers(
        correct_answers=payload.get("correct_answers"),
        total_questions=payload.get("total_questions"),
    )
    if by_correct is not None:
        return by_correct

    size = _extract_vocab_size_for_cefr(payload)
    if size is None:
        return None

    if size < 1000:
        return "A1"
    if size < 2000:
        return "A2"
    if size < 4000:
        return "B1"
    if size < 6000:
        return "B2"
    return "C1"


def _render_cefr_scale(level: str | None) -> str:
    levels = ["A0", "A1", "A1+", "A2", "B1", "B2", "C1", "C1+"]
    active = (level or "").upper()

    parts: list[str] = []
    for item in levels:
        if item == active:
            parts.append(f"🟩 {item}")
        else:
            parts.append(item)

    return " — ".join(parts)


def _peer_comparison_fallback(payload: dict[str, object], level: str | None) -> str:
    explicit = str(payload.get("peer_comparison_text") or "").strip()
    if explicit:
        return explicit
    return "Это типичный результат для этого диапазона."




def _add_previous_test_separator(text: str) -> str:
    if "Ваш прошлый тест:" not in text or "────────" in text:
        return text
    return re.sub(
        r"\n{2,}Ваш прошлый тест:",
        "\n\n────────\n\nВаш прошлый тест:",
        text,
        count=1,
    )

def _previous_result_block(payload: dict[str, object]) -> list[str]:
    prev_correct = payload.get("previous_correct_answers")
    prev_total = payload.get("previous_total_questions")
    prev_band = payload.get("previous_estimated_vocab_band")
    prev_size = payload.get("previous_estimated_vocab_size")

    if prev_correct is None or prev_total is None or (prev_band is None and prev_size is None):
        return []

    compact = None
    if prev_band is not None:
        band = str(prev_band)
        mapping = {
            "<500": "<500",
            "500-1000": "500–1 000",
            "1000-1500": "1 000–1 500",
            "1500-2500": "1 500–2 500",
            "2500-4000": "2 500–4 000",
            "4000-6000": "4 000–6 000",
            "6000-8000": "6 000–8 000",
            "8k+": "8000+",
            "<1.5k": "<1500",
            "1.5k-2.5k": "1 500–2 500",
            "2.5k-4k": "2 500–4 000",
            "4k-6k": "4 000–6 000",
            "6k-8k": "6 000–8 000",
        }
        compact = mapping.get(band)

    if compact is None and prev_size is not None:
        size = int(prev_size or 0)
        if size < 500:
            compact = "<500"
        elif size < 1000:
            compact = "500–1 000"
        elif size < 1500:
            compact = "1 000–1 500"
        elif size < 2500:
            compact = "1 500–2 500"
        elif size < 4000:
            compact = "2 500–4 000"
        elif size < 6000:
            compact = "4 000–6 000"
        elif size < 8000:
            compact = "6 000–8 000"
        else:
            compact = "8000+"

    if compact is None:
        return []

    prev_correct_i = int(prev_correct)
    prev_total_i = int(prev_total)

    return [
        "Ваш прошлый тест:",
        f"{prev_correct_i}/{prev_total_i} {_ru_plural_answer(prev_correct_i)} правильно и запас {compact} слов.",
    ]


def present_finished(payload: dict[str, object]) -> str:
    text = _ORIGINAL_PRESENT_FINISHED(payload)

    if "Ориентировочно это соответствует уровню" in text:
        return _add_previous_test_separator(text)

    level = _estimate_cefr_level_from_payload(payload)
    if not level:
        return _add_previous_test_separator(text)

    peer_text = _peer_comparison_fallback(payload, level)
    insert_block = [
        f"Ориентировочно это соответствует уровню {level}.",
        "",
        _render_cefr_scale(level),
    ]
    if peer_text:
        insert_block.extend(["", peer_text])

    previous_block = _previous_result_block(payload)
    lines = text.splitlines()

    insert_after = None
    for idx, line in enumerate(lines):
        if "Ваш пассивный словарный запас находится" in line:
            insert_after = idx + 1
            while insert_after < len(lines) and lines[insert_after] == "":
                insert_after += 1
            break

    if insert_after is None:
        rendered = text.rstrip() + "\n\n" + "\n".join(insert_block)
        if previous_block:
            approx = "Выводы этого теста приблизительны, они основаны на частотности слов и точности ваших ответов."
            if approx in rendered:
                rendered = rendered.replace(approx, "────────\n\n" + "\n".join(previous_block) + "\n\n" + approx, 1)
            else:
                rendered = rendered.rstrip() + "\n────────\n\n" + "\n".join(previous_block)
        return rendered

    new_lines = lines[:insert_after] + insert_block + [""] + lines[insert_after:]

    if previous_block:
        approx_idx = None
        for idx, line in enumerate(new_lines):
            if line == "Выводы этого теста приблизительны, они основаны на частотности слов и точности ваших ответов.":
                approx_idx = idx
                break
        if approx_idx is not None:
            new_lines = new_lines[:approx_idx] + ["────────", ""] + previous_block + [""] + new_lines[approx_idx:]

    return "\n".join(new_lines)
