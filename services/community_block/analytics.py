from __future__ import annotations

from services.community_block import repo


def mark_followup_sent(conn, *, post_log_id: int) -> None:
    repo.mark_followup_sent(conn, post_log_id=post_log_id)
