from __future__ import annotations


def _band_to_range_bounds(band: str, size: int) -> tuple[int | None, int | None]:
    mapping = {
        "<1.5k": (0, 1500),
        "1.5k-2.5k": (1500, 2500),
        "2.5k-4k": (2500, 4000),
        "4k-6k": (4000, 6000),
        "6k-8k": (6000, 8000),
        "8k+": (8000, None),
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
        f"Вы правильно ответили на {correct} вопросов из {total}.",
        "",
        f"Ваш пассивный словарный запас находится в диапазоне {_band_to_range_text(band, size)}.",
        "",
        "Оценка результата приблизительная, она основана на частотности слов и ваших ответах.",
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

    return "\n".join(lines)


def present_question(view: dict[str, object]) -> str:
    return str(view["text"])

# === VOCAB RESULT CEFR EXTENSION ===

import re as _re_vocab_cefr


_ORIGINAL_PRESENT_FINISHED = present_finished


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
    if explicit in {"A1", "A2", "B1", "B2", "C1"}:
        return explicit

    size = _extract_vocab_size_for_cefr(payload)
    if size is None:
        return None

    if size < 1000:
        return "A1"
    if size < 2500:
        return "A2"
    if size < 4000:
        return "B1"
    if size < 7000:
        return "B2"
    return "C1"


def _render_cefr_scale(level: str | None) -> str:
    levels = ["A1", "A2", "B1", "B2", "C1"]
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
            "<1.5k": "до 1 500",
            "1.5k-2.5k": "1 500–2 500",
            "2.5k-4k": "2 500–4 000",
            "4k-6k": "4 000–6 000",
            "6k-8k": "6 000–8 000",
            "8k+": "от 8 000",
        }
        compact = mapping.get(band)

    if compact is None and prev_size is not None:
        size = int(prev_size or 0)
        if size < 1500:
            compact = "до 1 500"
        elif size < 2500:
            compact = "1 500–2 500"
        elif size < 4000:
            compact = "2 500–4 000"
        elif size < 6000:
            compact = "4 000–6 000"
        elif size < 8000:
            compact = "6 000–8 000"
        else:
            compact = "от 8 000"

    if compact is None:
        return []

    return [
        "Ваш прошлый результат:",
        f"{int(prev_correct)}/{int(prev_total)} правильных ответов и оценка запаса в {compact} слов.",
    ]


def present_finished(payload: dict[str, object]) -> str:
    text = _ORIGINAL_PRESENT_FINISHED(payload)

    if "Ориентировочно это соответствует уровню" in text:
        return text

    level = _estimate_cefr_level_from_payload(payload)
    if not level:
        return text

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
            approx = "Оценка результата приблизительная, она основана на частотности слов и ваших ответах."
            if approx in rendered:
                rendered = rendered.replace(approx, "\n".join(previous_block) + "\n\n" + approx, 1)
            else:
                rendered = rendered.rstrip() + "\n\n" + "\n".join(previous_block)
        return rendered

    new_lines = lines[:insert_after] + insert_block + [""] + lines[insert_after:]

    if previous_block:
        approx_idx = None
        for idx, line in enumerate(new_lines):
            if line == "Оценка результата приблизительная, она основана на частотности слов и ваших ответах.":
                approx_idx = idx
                break
        if approx_idx is not None:
            new_lines = new_lines[:approx_idx] + [""] + previous_block + [""] + new_lines[approx_idx:]

    return "\n".join(new_lines)
