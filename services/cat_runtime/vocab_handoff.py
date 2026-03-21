from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from .item_model import CATItemModel
from .vocab_bridge import (
    build_cat_session_id,
    start_mode_cat_bridge,
    answer_mode_cat_bridge,
)


@dataclass(slots=True)
class CATVocabHandoff:
    user_id: int
    attempt_id: int
    mode: str
    session_id: str
    metadata: dict[str, Any]


def build_vocab_cat_handoff(
    *,
    user_id: int,
    attempt_id: int,
    mode: str = "vocab",
    metadata: dict[str, Any] | None = None,
) -> CATVocabHandoff:
    session_id = build_cat_session_id(
        user_id=int(user_id),
        mode=str(mode),
        attempt_id=int(attempt_id),
    )

    payload = dict(metadata or {})
    payload.setdefault("source_mode", str(mode))
    payload.setdefault("attempt_id", int(attempt_id))
    payload.setdefault("user_id", int(user_id))

    return CATVocabHandoff(
        user_id=int(user_id),
        attempt_id=int(attempt_id),
        mode=str(mode),
        session_id=session_id,
        metadata=payload,
    )


def start_vocab_cat_handoff(
    conn,
    *,
    user_id: int,
    attempt_id: int,
    feature_enabled: bool,
    item_bank: Sequence[CATItemModel] | None = None,
    started_at: str | None = None,
    metadata: dict[str, Any] | None = None,
    active_only: bool = True,
    limit: int | None = None,
):
    handoff = build_vocab_cat_handoff(
        user_id=int(user_id),
        attempt_id=int(attempt_id),
        mode="vocab",
        metadata=metadata,
    )

    return start_mode_cat_bridge(
        conn,
        user_id=handoff.user_id,
        mode=handoff.mode,
        feature_enabled=feature_enabled,
        item_bank=item_bank,
        attempt_id=handoff.attempt_id,
        started_at=started_at,
        metadata=handoff.metadata,
        active_only=active_only,
        limit=limit,
    )


def answer_vocab_cat_handoff(
    conn,
    *,
    user_id: int,
    attempt_id: int,
    item: CATItemModel,
    response_value: int | float,
    is_correct: bool,
    item_bank: Sequence[CATItemModel] | None = None,
    updated_at: str | None = None,
):
    return answer_mode_cat_bridge(
        conn,
        user_id=int(user_id),
        mode="vocab",
        item=item,
        response_value=response_value,
        is_correct=is_correct,
        item_bank=item_bank,
        attempt_id=int(attempt_id),
        updated_at=updated_at,
    )
