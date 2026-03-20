from __future__ import annotations

import sqlite3
from pathlib import Path

from services.community_block import ai_repo, repo
from services.community_block.ai_planner import build_plan
from services.community_block.bootstrap import bootstrap_community_layer


def apply_all_sqlite_migrations(conn: sqlite3.Connection) -> None:
    migrations_dir = Path("db/migrations_sqlite")
    for path in sorted(migrations_dir.glob("*.sql")):
        conn.executescript(path.read_text(encoding="utf-8"))


def build_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    apply_all_sqlite_migrations(conn)
    bootstrap_community_layer(conn)
    conn.commit()
    return conn


def seed_base_thread(conn: sqlite3.Connection) -> int:
    repo.bind_chat_identity(
        conn,
        chat_key="chatalgarve",
        real_chat_id=-1001690275466,
        has_topics=False,
        default_topic_id=None,
    )
    repo.enable_only_chat(conn, chat_key="chatalgarve")

    content_id = repo.create_content_item(
        conn,
        text="Какими словами лучше намекнуть продавцу, что preço fixo звучит смело, но рынок видит это иначе?",
        format_type="nuance",
        topic="financas",
        region="algarve",
        has_question=True,
        difficulty="light",
        is_active=True,
        priority=10,
    )
    post_log_id = repo.log_post(
        conn,
        chat_id=-1001690275466,
        content_id=content_id,
        thread_root_message_id=60033,
        posted_message_id=60033,
    )
    conn.commit()
    return post_log_id


def test_planner_allows_second_reply_after_one_sent_ai_reply() -> None:
    conn = build_conn()
    post_log_id = seed_base_thread(conn)

    repo.record_thread_event_rich(
        conn,
        chat_id=-1001690275466,
        post_log_id=post_log_id,
        thread_root_message_id=60033,
        message_id=60034,
        user_id=42,
        event_type="user_reply",
        message_thread_id=60033,
        reply_to_message_id=60033,
        message_text="А как это реально говорят?",
    )
    repo.record_thread_event_rich(
        conn,
        chat_id=-1001690275466,
        post_log_id=post_log_id,
        thread_root_message_id=60033,
        message_id=60035,
        user_id=0,
        event_type="ai_reply",
        message_thread_id=60033,
        reply_to_message_id=60034,
        message_text="По-португальски обычно так: ...",
    )
    repo.log_ai_reply_delivery(
        conn,
        chat_id=-1001690275466,
        post_log_id=post_log_id,
        plan_log_id=101,
        trigger_message_id=60034,
        reply_to_message_id=60034,
        sent_message_id=60035,
        delivery_status="sent_generated",
        provider="openai",
        model="gpt-5",
        response_id="resp_1",
        used_fallback=False,
        delivered_text="По-португальски обычно так: ...",
    )
    repo.record_thread_event_rich(
        conn,
        chat_id=-1001690275466,
        post_log_id=post_log_id,
        thread_root_message_id=60033,
        message_id=60036,
        user_id=42,
        event_type="user_reply",
        message_thread_id=60033,
        reply_to_message_id=60035,
        message_text="А если совсем по-простому?",
    )
    conn.commit()

    snapshot = ai_repo.fetch_thread_snapshot(conn, post_log_id=post_log_id)
    assert snapshot.prior_ai_plan_count == 1

    decision = build_plan(snapshot, min_user_replies=1, max_plans_per_thread=2)
    assert decision.should_reply is True
    assert decision.reason == "planned_candidate_selected"


def test_planner_blocks_after_two_sent_ai_replies() -> None:
    conn = build_conn()
    post_log_id = seed_base_thread(conn)

    repo.record_thread_event_rich(
        conn,
        chat_id=-1001690275466,
        post_log_id=post_log_id,
        thread_root_message_id=60033,
        message_id=60034,
        user_id=42,
        event_type="user_reply",
        message_thread_id=60033,
        reply_to_message_id=60033,
        message_text="Первый вопрос",
    )
    repo.record_thread_event_rich(
        conn,
        chat_id=-1001690275466,
        post_log_id=post_log_id,
        thread_root_message_id=60033,
        message_id=60035,
        user_id=0,
        event_type="ai_reply",
        message_thread_id=60033,
        reply_to_message_id=60034,
        message_text="Первый ответ AI",
    )
    repo.log_ai_reply_delivery(
        conn,
        chat_id=-1001690275466,
        post_log_id=post_log_id,
        plan_log_id=101,
        trigger_message_id=60034,
        reply_to_message_id=60034,
        sent_message_id=60035,
        delivery_status="sent_generated",
        provider="openai",
        model="gpt-5",
        response_id="resp_1",
        used_fallback=False,
        delivered_text="Первый ответ AI",
    )

    repo.record_thread_event_rich(
        conn,
        chat_id=-1001690275466,
        post_log_id=post_log_id,
        thread_root_message_id=60033,
        message_id=60036,
        user_id=42,
        event_type="user_reply",
        message_thread_id=60033,
        reply_to_message_id=60035,
        message_text="Второй вопрос",
    )
    repo.record_thread_event_rich(
        conn,
        chat_id=-1001690275466,
        post_log_id=post_log_id,
        thread_root_message_id=60033,
        message_id=60037,
        user_id=0,
        event_type="ai_reply",
        message_thread_id=60033,
        reply_to_message_id=60036,
        message_text="Второй ответ AI",
    )
    repo.log_ai_reply_delivery(
        conn,
        chat_id=-1001690275466,
        post_log_id=post_log_id,
        plan_log_id=102,
        trigger_message_id=60036,
        reply_to_message_id=60036,
        sent_message_id=60037,
        delivery_status="sent_generated",
        provider="openai",
        model="gpt-5",
        response_id="resp_2",
        used_fallback=False,
        delivered_text="Второй ответ AI",
    )

    repo.record_thread_event_rich(
        conn,
        chat_id=-1001690275466,
        post_log_id=post_log_id,
        thread_root_message_id=60033,
        message_id=60038,
        user_id=42,
        event_type="user_reply",
        message_thread_id=60033,
        reply_to_message_id=60037,
        message_text="Третий вопрос",
    )
    conn.commit()

    snapshot = ai_repo.fetch_thread_snapshot(conn, post_log_id=post_log_id)
    assert snapshot.prior_ai_plan_count == 2

    decision = build_plan(snapshot, min_user_replies=1, max_plans_per_thread=2)
    assert decision.should_reply is False
    assert decision.reason == "max_plans_reached"
