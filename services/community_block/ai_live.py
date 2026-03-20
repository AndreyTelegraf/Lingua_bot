from __future__ import annotations

import sqlite3

from services.community_block import repo
from services.community_block.ai_generator import generate_from_prompt_payload
from services.community_block.ai_validator import validate_generated_text
from services.community_block.sender import send_thread_reply


async def maybe_send_live_reply(
    conn: sqlite3.Connection,
    *,
    bot,
    planned: dict | None,
    chat_id: int,
    post_log_id: int,
    trigger_message_id: int,
    message_thread_id: int | None,
) -> dict:
    if not planned:
        return {"status": "skipped", "reason": "no_plan"}

    decision = planned.get("decision") or {}
    if not decision.get("should_reply"):
        return {"status": "skipped", "reason": "plan_says_no_reply"}

    if str(repo.get_runtime_flag(conn, key="ai_live_enabled", default="0") or "0") != "1":
        return {"status": "skipped", "reason": "ai_live_disabled"}

    plan_log_id = int(planned["plan_log_id"])
    if repo.has_ai_delivery_for_plan(conn, plan_log_id=plan_log_id):
        return {"status": "skipped", "reason": "delivery_already_exists", "plan_log_id": plan_log_id}

    cooldown_seconds = repo.get_runtime_int(conn, key="ai_reply_cooldown_seconds", default=900)
    if repo.has_recent_ai_delivery_for_post(conn, post_log_id=post_log_id, cooldown_seconds=cooldown_seconds):
        delivery_log_id = repo.log_ai_reply_delivery(
            conn,
            chat_id=chat_id,
            post_log_id=post_log_id,
            plan_log_id=plan_log_id,
            trigger_message_id=trigger_message_id,
            reply_to_message_id=trigger_message_id,
            sent_message_id=None,
            delivery_status="skipped_cooldown",
            delivered_text=None,
        )
        conn.commit()
        return {"status": "skipped", "reason": "thread_cooldown_active", "delivery_log_id": delivery_log_id}

    max_chars = repo.get_runtime_int(conn, key="ai_max_generated_chars", default=220)
    fallback_allowed = str(repo.get_runtime_flag(conn, key="ai_fallback_to_planner_text", default="1") or "1") == "1"

    generated = generate_from_prompt_payload(planned["prompt_payload"])
    validation = validate_generated_text(generated.text, max_chars=max_chars)

    final_text = None
    used_fallback = False
    delivery_status = None

    if validation.ok:
        final_text = validation.cleaned_text
        delivery_status = "sent_generated"
    elif fallback_allowed:
        fallback_text = str(decision.get("selected_reply_text") or "").strip()
        fallback_validation = validate_generated_text(fallback_text, max_chars=max_chars)
        if fallback_validation.ok:
            final_text = fallback_validation.cleaned_text
            used_fallback = True
            delivery_status = "sent_fallback"
        else:
            delivery_log_id = repo.log_ai_reply_delivery(
                conn,
                chat_id=chat_id,
                post_log_id=post_log_id,
                plan_log_id=plan_log_id,
                trigger_message_id=trigger_message_id,
                reply_to_message_id=trigger_message_id,
                sent_message_id=None,
                delivery_status="rejected_invalid_output",
                provider=generated.provider,
                model=generated.model,
                response_id=generated.response_id,
                used_fallback=False,
                delivered_text=validation.cleaned_text or generated.text,
            )
            conn.commit()
            return {
                "status": "rejected",
                "reason": f"invalid_generated_and_fallback:{validation.reason}",
                "delivery_log_id": delivery_log_id,
            }
    else:
        delivery_log_id = repo.log_ai_reply_delivery(
            conn,
            chat_id=chat_id,
            post_log_id=post_log_id,
            plan_log_id=plan_log_id,
            trigger_message_id=trigger_message_id,
            reply_to_message_id=trigger_message_id,
            sent_message_id=None,
            delivery_status="rejected_invalid_output",
            provider=generated.provider,
            model=generated.model,
            response_id=generated.response_id,
            used_fallback=False,
            delivered_text=validation.cleaned_text or generated.text,
        )
        conn.commit()
        return {
            "status": "rejected",
            "reason": f"invalid_generated:{validation.reason}",
            "delivery_log_id": delivery_log_id,
        }

    sent_message_id = await send_thread_reply(
        bot,
        chat_id=chat_id,
        text=final_text,
        reply_to_message_id=trigger_message_id,
        message_thread_id=message_thread_id,
    )

    repo.record_thread_event_rich(
        conn,
        chat_id=chat_id,
        post_log_id=post_log_id,
        thread_root_message_id=None,
        message_id=sent_message_id,
        user_id=0,
        event_type="ai_reply",
        message_thread_id=message_thread_id,
        reply_to_message_id=trigger_message_id,
        message_text=final_text,
    )

    delivery_log_id = repo.log_ai_reply_delivery(
        conn,
        chat_id=chat_id,
        post_log_id=post_log_id,
        plan_log_id=plan_log_id,
        trigger_message_id=trigger_message_id,
        reply_to_message_id=trigger_message_id,
        sent_message_id=sent_message_id,
        delivery_status=delivery_status,
        provider=generated.provider,
        model=generated.model,
        response_id=generated.response_id,
        used_fallback=used_fallback,
        delivered_text=final_text,
    )
    conn.commit()

    return {
        "status": "sent",
        "delivery_status": delivery_status,
        "delivery_log_id": delivery_log_id,
        "sent_message_id": sent_message_id,
        "used_fallback": used_fallback,
        "text": final_text,
    }
