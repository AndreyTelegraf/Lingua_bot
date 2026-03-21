from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from .item_model import CATItemModel
from .vocab_answer_entry import continue_vocab_runtime_cat_entry, decide_vocab_cat_answer
from .vocab_entry import start_vocab_runtime_cat_entry, decide_vocab_cat_entry


@dataclass(slots=True)
class CATVocabRuntimeRouteResult:
    use_cat: bool
    reason: str | None
    route: str
    result: Any | None


def route_vocab_runtime_cat_start(
    conn,
    *,
    user_id: int,
    attempt_id: int,
    feature_enabled: bool,
    mode: str = "vocab",
    item_bank: Sequence[CATItemModel] | None = None,
    started_at: str | None = None,
    metadata: dict[str, Any] | None = None,
    active_only: bool = True,
    limit: int | None = None,
) -> CATVocabRuntimeRouteResult:
    decision = decide_vocab_cat_entry(
        user_id=int(user_id),
        attempt_id=int(attempt_id),
        mode=str(mode),
        feature_enabled=feature_enabled,
        metadata=metadata,
    )
    if not decision.use_cat:
        return CATVocabRuntimeRouteResult(
            use_cat=False,
            reason=decision.reason,
            route="noop",
            result=None,
        )

    started = start_vocab_runtime_cat_entry(
        conn,
        user_id=int(user_id),
        attempt_id=int(attempt_id),
        feature_enabled=feature_enabled,
        mode=str(mode),
        item_bank=item_bank,
        started_at=started_at,
        metadata=metadata,
        active_only=active_only,
        limit=limit,
    )
    return CATVocabRuntimeRouteResult(
        use_cat=True,
        reason=None,
        route="start",
        result=started,
    )


def route_vocab_runtime_cat_answer(
    conn,
    *,
    user_id: int,
    attempt_id: int,
    feature_enabled: bool,
    item: CATItemModel,
    response_value: int | float,
    is_correct: bool,
    mode: str = "vocab",
    item_bank: Sequence[CATItemModel] | None = None,
    updated_at: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> CATVocabRuntimeRouteResult:
    decision = decide_vocab_cat_answer(
        user_id=int(user_id),
        attempt_id=int(attempt_id),
        mode=str(mode),
        feature_enabled=feature_enabled,
        metadata=metadata,
    )
    if not decision.use_cat:
        return CATVocabRuntimeRouteResult(
            use_cat=False,
            reason=decision.reason,
            route="noop",
            result=None,
        )

    step = continue_vocab_runtime_cat_entry(
        conn,
        user_id=int(user_id),
        attempt_id=int(attempt_id),
        feature_enabled=feature_enabled,
        item=item,
        response_value=response_value,
        is_correct=is_correct,
        mode=str(mode),
        item_bank=item_bank,
        updated_at=updated_at,
        metadata=metadata,
    )
    return CATVocabRuntimeRouteResult(
        use_cat=True,
        reason=None,
        route="answer",
        result=step,
    )
