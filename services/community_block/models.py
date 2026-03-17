from __future__ import annotations

from dataclasses import dataclass

COMMUNITY_ACTIVE_STATUSES = ("enabled", "disabled")
COMMUNITY_EVENT_TYPES = ("user_reply", "bot_followup", "bot_summary")

COMMUNITY_RUNTIME_KEYS = {
    "global_enabled": "1",
    "followups_enabled": "0",
    "default_mode": "A",
}


@dataclass(slots=True)
class CommunityChat:
    chat_id: int
    chat_key: str
    chat_type: str
    region: str | None
    has_topics: bool
    default_topic_id: int | None
    is_enabled: bool
    daily_post_time: str
    max_posts_per_day: int
    cooldown_hours: int


@dataclass(slots=True)
class CommunityContentItem:
    id: int
    text: str
    format_type: str
    topic: str | None
    region: str | None
    has_question: bool
    difficulty: str
    is_active: bool
    priority: int


@dataclass(slots=True)
class CommunityPostLog:
    id: int
    chat_id: int
    content_id: int
    thread_root_message_id: int | None
    posted_message_id: int | None
    had_replies: bool
    replies_count: int
    unique_users_count: int
    reply_latency_first_sec: int | None
    thread_depth_max: int
    followup_sent: bool
    thread_reactivated_after_followup: bool


@dataclass(slots=True)
class CommunityThreadEvent:
    id: int
    chat_id: int
    post_log_id: int | None
    thread_root_message_id: int | None
    message_id: int
    user_id: int
    event_type: str
