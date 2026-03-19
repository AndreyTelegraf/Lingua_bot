from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from services.community_block import repo
from services.community_block.policy import (
    ACTIVE_DISCUSSION_MESSAGE_THRESHOLD,
    ANTI_REPEAT_DAYS_PER_CHAT,
)
from services.community_block.scheduler import (
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
    exclude_content_ids: set[int] | None = None,
) -> CommunityDecision:
    chat_id = int(chat["chat_id"])

    if not bool(chat.get("is_enabled")):
        return CommunityDecision(
            allowed=False,
            reason="chat_disabled",
            chat_id=chat_id,
            dry_run=dry_run,
        )

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
            chat_id=chat_id,
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
            chat_id=chat_id,
            dry_run=dry_run,
        )

    recent_formats = repo.get_recent_format_types_for_chat(
        conn,
        chat_id=chat_id,
        limit=3,
    )
    excluded_format_type = recent_formats[0] if recent_formats else None

    candidates = repo.list_candidate_content(
        conn,
        region=chat.get("region"),
        excluded_format_type=excluded_format_type,
    )

    used_content_ids = repo.list_used_content_ids_for_chat(
        conn,
        chat_id=chat_id,
    )
    excluded_content_ids = exclude_content_ids or set()

    def _format_allowed(format_type: str) -> bool:
        return repo.count_recent_format_type_usage(
            conn,
            chat_id=chat_id,
            format_type=format_type,
            limit=3,
        ) < 2

    never_used_candidates = [
        candidate
        for candidate in candidates
        if int(candidate["id"]) not in used_content_ids
        and int(candidate["id"]) not in excluded_content_ids
        and _format_allowed(str(candidate["format_type"]))
    ]
    if never_used_candidates:
        candidate = never_used_candidates[0]
        return CommunityDecision(
            allowed=True,
            reason="candidate_selected_fresh",
            chat_id=chat_id,
            content_id=int(candidate["id"]),
            content_format_type=str(candidate["format_type"]),
            dry_run=dry_run,
        )

    reusable_candidates = [
        candidate
        for candidate in candidates
        if int(candidate["id"]) not in excluded_content_ids
        and _format_allowed(str(candidate["format_type"]))
    ]
    if reusable_candidates:
        candidate = reusable_candidates[0]
        return CommunityDecision(
            allowed=True,
            reason="candidate_selected_reuse_after_exhaustion",
            chat_id=chat_id,
            content_id=int(candidate["id"]),
            content_format_type=str(candidate["format_type"]),
            dry_run=dry_run,
        )

    fallback_candidates = [
        candidate
        for candidate in repo.list_candidate_content(
            conn,
            region=chat.get("region"),
            excluded_format_type=None,
        )
        if int(candidate["id"]) not in excluded_content_ids
        and _format_allowed(str(candidate["format_type"]))
    ]
    if fallback_candidates:
        candidate = fallback_candidates[0]
        return CommunityDecision(
            allowed=True,
            reason="candidate_selected_format_fallback",
            chat_id=chat_id,
            content_id=int(candidate["id"]),
            content_format_type=str(candidate["format_type"]),
            dry_run=dry_run,
        )

    return CommunityDecision(
        allowed=False,
        reason="no_candidate",
        chat_id=chat_id,
        dry_run=dry_run,
    )

