from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .vocab_fsm_wiring import (
    maybe_continue_cat_from_vocab_attempt_answer,
    maybe_start_cat_from_vocab_attempt,
)


@dataclass(slots=True)
class CATVocabPatchedStart:
    source: str
    use_cat: bool
    route_result: Any | None


@dataclass(slots=True)
class CATVocabPatchedAnswer:
    source: str
    use_cat: bool
    route_result: Any | None


def patchable_start_from_vocab_runtime(
    conn,
    *,
    user_id: int,
    attempt_id: int,
    feature_enabled: bool,
    item_bank=None,
    started_at: str | None = None,
    metadata: dict[str, Any] | None = None,
    active_only: bool = True,
    limit: int | None = None,
) -> CATVocabPatchedStart:
    routed = maybe_start_cat_from_vocab_attempt(
        conn,
        user_id=int(user_id),
        attempt_id=int(attempt_id),
        feature_enabled=feature_enabled,
        mode="vocab",
        item_bank=item_bank,
        started_at=started_at,
        metadata=metadata,
        active_only=active_only,
        limit=limit,
    )
    return CATVocabPatchedStart(
        source=routed.source,
        use_cat=bool(routed.use_cat),
        route_result=routed.route_result,
    )


def patchable_answer_from_vocab_runtime(
    conn,
    *,
    user_id: int,
    attempt_id: int,
    feature_enabled: bool,
    item,
    response_value: int | float,
    is_correct: bool,
    item_bank=None,
    updated_at: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> CATVocabPatchedAnswer:
    routed = maybe_continue_cat_from_vocab_attempt_answer(
        conn,
        user_id=int(user_id),
        attempt_id=int(attempt_id),
        feature_enabled=feature_enabled,
        mode="vocab",
        item=item,
        response_value=response_value,
        is_correct=is_correct,
        item_bank=item_bank,
        updated_at=updated_at,
        metadata=metadata,
    )
    return CATVocabPatchedAnswer(
        source=routed.source,
        use_cat=bool(routed.use_cat),
        route_result=routed.route_result,
    )
