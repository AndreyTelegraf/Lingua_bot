from __future__ import annotations


def present_finished(payload: dict[str, object]) -> str:
    summary_text = payload.get("summary_text")
    if summary_text:
        return str(summary_text)

    total = int(payload.get("total_questions", 0))
    correct = int(payload.get("correct_answers", 0))
    accuracy_pct = float(payload.get("accuracy_pct", 0.0))
    accuracy_text = str(int(accuracy_pct)) if float(accuracy_pct).is_integer() else str(accuracy_pct)

    lines = [f"Vocab finished. Score: {correct}/{total} ({accuracy_text}%)"]

    estimated_vocab_size = payload.get("estimated_vocab_size")
    estimated_vocab_band = payload.get("estimated_vocab_band")
    confidence = payload.get("confidence")

    if estimated_vocab_size is not None:
        lines.append(f"Estimated vocabulary: ~{int(estimated_vocab_size)} words")
    if estimated_vocab_band:
        lines.append(f"Band: {estimated_vocab_band}")
    if confidence is not None:
        lines.append(f"Confidence: {round(float(confidence) * 100)}%")

    return "\n".join(lines)


def present_question(view: dict[str, object]) -> str:
    return str(view["text"])
