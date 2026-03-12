from __future__ import annotations


def present_finished(payload: dict[str, object]) -> str:
    total = int(payload.get('total_questions', 0))
    correct = int(payload.get('correct_answers', 0))
    return f'Vocab finished. Score: {correct}/{total}'


def present_question(view: dict[str, object]) -> str:
    return str(view['text'])
