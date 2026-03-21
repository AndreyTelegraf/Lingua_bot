from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from .item_model import CATItemModel
from .vocab_runtime_router import (
    CATVocabRuntimeRouteResult,
    route_vocab_runtime_cat_answer,
    route_vocab_runtime_cat_start,
)


@dataclass(slots=True)
class CATVocabFSMStartRoute:
    use_cat: bool
    source: str
    route_result: CATVocabRuntimeRouteResult | None


@dataclass(slots=True)
class CATVocabFSMAnswerRoute:
    use_cat: bool
    source: str
    route_result: CATVocabRuntimeRouteResult | None


def maybe_start_cat_from_vocab_attempt(
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
) -> CATVocabFSMStartRoute:
    routed = route_vocab_runtime_cat_start(
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
    if not routed.use_cat:
        return CATVocabFSMStartRoute(
            use_cat=False,
            source="legacy",
            route_result=routed,
        )
    return CATVocabFSMStartRoute(
        use_cat=True,
        source="cat",
        route_result=routed,
    )


def maybe_continue_cat_from_vocab_attempt_answer(
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
) -> CATVocabFSMAnswerRoute:
    routed = route_vocab_runtime_cat_answer(
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
    if not routed.use_cat:
        return CATVocabFSMAnswerRoute(
            use_cat=False,
            source="legacy",
            route_result=routed,
        )
    return CATVocabFSMAnswerRoute(
        use_cat=True,
        source="cat",
        route_result=routed,
    )
