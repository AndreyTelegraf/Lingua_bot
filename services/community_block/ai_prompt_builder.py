from __future__ import annotations

from .ai_policy import PlanDecision, ThreadSnapshot


SYSTEM_PROMPT = (
    "Ты пишешь как живой русскоязычный участник локального чата в Португалии. "
    "Ты не саппорт, не юрист, не врач и не продавец. "
    "Твоя задача — иногда коротко и естественно поддерживать уже начавшийся разговор. "
    "Не пиши длинно. Не используй списки, канцелярит, экспертные вводные и рекламный тон. "
    "Не выгляди как AI. Лучше недосказать, чем написать слишком правильно. "
    "Если не уверен в факте — не утверждай его."
)


def render_thread(snapshot: ThreadSnapshot) -> str:
    lines: list[str] = []
    for idx, msg in enumerate(snapshot.messages[-8:]):
        role = "seed" if idx == 0 and msg.role == "seed" else msg.role
        lines.append(f"{role}: {msg.text}")
    return "\n".join(lines)


def build_prompt_payload(snapshot: ThreadSnapshot, decision: PlanDecision) -> dict:
    developer_prompt = (
        f"chat_key={snapshot.chat_key}; chat_type={snapshot.chat_type}; "
        f"region={snapshot.region or ''}; topic={snapshot.topic or ''}; "
        f"format_type={snapshot.format_type or ''}; risk={decision.risk_level}; "
        f"reply_mode={decision.reply_mode}; "
        f"should_reply={int(decision.should_reply)}."
    )
    user_prompt = (
        "Ниже текущий тред. Сгенерируй один короткий естественный ответ, "
        "который не выглядит как бот. Не используй списки и не делай вывод-резюме.\n\n"
        f"{render_thread(snapshot)}"
    )
    return {
        "system_prompt": SYSTEM_PROMPT,
        "developer_prompt": developer_prompt,
        "user_prompt": user_prompt,
        "metadata": {
            "post_log_id": snapshot.post_log_id,
            "chat_id": snapshot.chat_id,
            "thread_root_message_id": snapshot.thread_root_message_id,
            "chat_key": snapshot.chat_key,
            "topic": snapshot.topic,
            "format_type": snapshot.format_type,
            "reply_mode": decision.reply_mode,
            "risk_level": decision.risk_level,
            "candidate_texts": [c.text for c in decision.candidates],
        },
    }
