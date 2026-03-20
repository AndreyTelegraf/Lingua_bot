from __future__ import annotations

from dataclasses import replace

from . import ai_repo
from .ai_policy import (
    CandidateReply,
    PlanDecision,
    ThreadSnapshot,
    base_fit_to_thread,
    brevity_score,
    canned_pattern_score,
    choose_reply_mode,
    classify_risk,
    has_terminal_question,
    human_like_score,
    topic_candidate_texts,
    verbosity_score,
)
from .ai_prompt_builder import build_prompt_payload


def _last_user_message(snapshot: ThreadSnapshot) -> str:
    for msg in reversed(snapshot.messages):
        if msg.role == "user":
            return msg.text
    return ""


def _candidate_from_text(snapshot: ThreadSnapshot, text: str) -> CandidateReply:
    canned = canned_pattern_score(text)
    verbose = verbosity_score(text)
    brief = brevity_score(text)
    fit = base_fit_to_thread(snapshot.topic, text)
    human = human_like_score(text)
    usefulness = 0.8 if snapshot.topic else 0.65
    non_salesiness = 1.0
    naturalness = max(0.0, min(1.0, (human * 0.65) + (brief * 0.2) + (fit * 0.15)))
    return CandidateReply(
        text=text,
        naturalness=naturalness,
        usefulness=usefulness,
        non_salesiness=non_salesiness,
        brevity=brief,
        fit_to_thread=fit,
        human_like_score=human,
        verbosity_score=verbose,
        canned_pattern_score=canned,
    )


def build_plan(snapshot: ThreadSnapshot, *, min_user_replies: int = 1, max_plans_per_thread: int = 2) -> PlanDecision:
    user_reply_count = ai_repo.count_user_reply_events(snapshot)
    ai_reply_count = ai_repo.count_ai_reply_events(snapshot)
    last_user_text = _last_user_message(snapshot)
    wants_answer = has_terminal_question(last_user_text)
    risk_level = classify_risk(snapshot.topic, last_user_text)

    if user_reply_count < min_user_replies:
        return PlanDecision(
            should_reply=False,
            reply_mode="R0",
            reason="no_user_replies_yet",
            confidence=1.0,
            risk_level=risk_level,
            product_bridge_allowed=False,
            human_like_score=1.0,
            verbosity_score=0.0,
            canned_pattern_score=0.0,
            selected_reply_text=None,
            candidates=[],
        )

    if ai_reply_count > 0:
        return PlanDecision(
            should_reply=False,
            reply_mode="R0",
            reason="existing_ai_reply_detected",
            confidence=1.0,
            risk_level=risk_level,
            product_bridge_allowed=False,
            human_like_score=1.0,
            verbosity_score=0.0,
            canned_pattern_score=0.0,
            selected_reply_text=None,
            candidates=[],
        )

    if snapshot.prior_ai_plan_count >= max_plans_per_thread:
        return PlanDecision(
            should_reply=False,
            reply_mode="R0",
            reason="max_plans_reached",
            confidence=1.0,
            risk_level=risk_level,
            product_bridge_allowed=False,
            human_like_score=1.0,
            verbosity_score=0.0,
            canned_pattern_score=0.0,
            selected_reply_text=None,
            candidates=[],
        )

    candidate_texts = topic_candidate_texts(snapshot.topic, wants_answer)
    candidates = [_candidate_from_text(snapshot, text) for text in candidate_texts]
    candidates.sort(
        key=lambda c: (
            c.human_like_score,
            c.naturalness,
            c.brevity,
            c.fit_to_thread,
            c.usefulness,
        ),
        reverse=True,
    )
    top = candidates[0]
    reply_mode = choose_reply_mode(risk_level, wants_answer)
    confidence = 0.55 if risk_level == "high" else 0.78 if wants_answer else 0.66

    return PlanDecision(
        should_reply=True,
        reply_mode=reply_mode,
        reason="planned_candidate_selected",
        confidence=confidence,
        risk_level=risk_level,
        product_bridge_allowed=False,
        human_like_score=top.human_like_score,
        verbosity_score=top.verbosity_score,
        canned_pattern_score=top.canned_pattern_score,
        selected_reply_text=top.text,
        candidates=candidates[:5],
    )


def plan_and_persist(conn, *, post_log_id: int, min_user_replies: int = 1, max_plans_per_thread: int = 2) -> dict:
    snapshot = ai_repo.fetch_thread_snapshot(conn, post_log_id=post_log_id)
    decision = build_plan(
        snapshot,
        min_user_replies=min_user_replies,
        max_plans_per_thread=max_plans_per_thread,
    )
    prompt_payload = build_prompt_payload(snapshot, decision)
    plan_log_id = ai_repo.insert_reply_plan_log(
        conn,
        snapshot=snapshot,
        decision=decision,
        prompt_payload=prompt_payload,
    )
    conn.commit()
    return {
        "post_log_id": snapshot.post_log_id,
        "plan_log_id": plan_log_id,
        "snapshot": {
            "chat_id": snapshot.chat_id,
            "chat_key": snapshot.chat_key,
            "chat_type": snapshot.chat_type,
            "region": snapshot.region,
            "thread_root_message_id": snapshot.thread_root_message_id,
            "topic": snapshot.topic,
            "format_type": snapshot.format_type,
            "seed_text": snapshot.seed_text,
            "messages": [
                {
                    "role": m.role,
                    "text": m.text,
                    "message_id": m.message_id,
                    "user_id": m.user_id,
                    "event_type": m.event_type,
                }
                for m in snapshot.messages
            ],
            "followup_sent": snapshot.followup_sent,
            "replies_count": snapshot.replies_count,
            "unique_users_count": snapshot.unique_users_count,
            "prior_ai_plan_count": snapshot.prior_ai_plan_count,
        },
        "decision": decision.as_dict(),
        "prompt_payload": prompt_payload,
    }
