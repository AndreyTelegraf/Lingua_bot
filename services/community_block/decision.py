from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from services.community_block import repo
from services.community_block.policy import (
    ACTIVE_DISCUSSION_MESSAGE_THRESHOLD,
    ANTI_REPEAT_DAYS_PER_CHAT,
)
from services.community_block.scheduler import (
    SchedulerDecision,
    should_skip_for_activity,
    should_skip_for_cooldown,
)


@dataclass(slots=True)
class CommunityDecision:
    allowed: bool
    reason: str
    chat_id: int
    content_id: int | None = None
    content_format_type: str | None = None
    dry_run: bool = True


def _parse_db_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace(" ", "T")).replace(tzinfo=UTC)


def choose_post_candidate(
    conn,
    *,
    chat: dict,
    recent_messages_count: int = 0,
    dry_run: bool = True,
) -> CommunityDecision:
    now = datetime.now(UTC)

    cooldown_check = should_skip_for_cooldown(
        now=now,
        last_posted_at=_parse_db_dt(chat.get("last_posted_at")),
        cooldown_hours=int(chat.get("cooldown_hours") or 24),
    )
    if not cooldown_check.allowed:
        return CommunityDecision(
            allowed=False,
            reason=cooldown_check.reason,
            chat_id=int(chat["chat_id"]),
            dry_run=dry_run,
        )

    activity_check = should_skip_for_activity(
        recent_messages_count=recent_messages_count,
        threshold=ACTIVE_DISCUSSION_MESSAGE_THRESHOLD,
    )
    if not activity_check.allowed:
        return CommunityDecision(
            allowed=False,
            reason=activity_check.reason,
            chat_id=int(chat["chat_id"]),
            dry_run=dry_run,
        )

    recent_formats = repo.get_recent_format_types_for_chat(
        conn,
        chat_id=int(chat["chat_id"]),
        limit=3,
    )
    excluded_format_type = recent_formats[0] if recent_formats else None

    candidates = repo.list_candidate_content(
        conn,
        region=chat.get("region"),
        excluded_format_type=excluded_format_type,
    )

    for candidate in candidates:
        content_id = int(candidate["id"])
        format_type = str(candidate["format_type"])

        if repo.was_content_used_in_chat_within_days(
            conn,
            chat_id=int(chat["chat_id"]),
            content_id=content_id,
            days=ANTI_REPEAT_DAYS_PER_CHAT,
        ):
            continue

        if repo.count_recent_format_type_usage(
            conn,
            chat_id=int(chat["chat_id"]),
            format_type=format_type,
            limit=3,
        ) >= 2:
            continue

        return CommunityDecision(
            allowed=True,
            reason="candidate_selected",
            chat_id=int(chat["chat_id"]),
            content_id=content_id,
            content_format_type=format_type,
            dry_run=dry_run,
        )

    return CommunityDecision(
        allowed=False,
        reason="no_candidate",
        chat_id=int(chat["chat_id"]),
        dry_run=dry_run,
    )
