from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from .item_model import CATItemModel
from .vocab_bridge import should_use_cat_for_mode
from .vocab_handoff import CATVocabHandoff, answer_vocab_cat_handoff, build_vocab_cat_handoff


@dataclass(slots=True)
class CATVocabAnswerDecision:
    use_cat: bool
    reason: str | None
    mode: str
    handoff: CATVocabHandoff | None


def decide_vocab_cat_answer(
    *,
    user_id: int,
    attempt_id: int,
    mode: str = "vocab",
    feature_enabled: bool,
    metadata: dict[str, Any] | None = None,
) -> CATVocabAnswerDecision:
    bridge = should_use_cat_for_mode(
        mode=mode,
        feature_enabled=feature_enabled,
    )
    if not bridge.enabled:
        return CATVocabAnswerDecision(
            use_cat=False,
            reason=bridge.reason,
            mode=str(mode),
            handoff=None,
        )

    handoff = build_vocab_cat_handoff(
        user_id=int(user_id),
        attempt_id=int(attempt_id),
        mode=str(mode),
        metadata=metadata,
    )
    return CATVocabAnswerDecision(
        use_cat=True,
        reason=None,
        mode=str(mode),
        handoff=handoff,
    )


def continue_vocab_runtime_cat_entry(
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
):
    decision = decide_vocab_cat_answer(
        user_id=int(user_id),
        attempt_id=int(attempt_id),
        mode=str(mode),
        feature_enabled=feature_enabled,
        metadata=metadata,
    )

    if not decision.use_cat:
        return None

    return answer_vocab_cat_handoff(
        conn,
        user_id=int(user_id),
        attempt_id=int(attempt_id),
        item=item,
        response_value=response_value,
        is_correct=is_correct,
        item_bank=item_bank,
        updated_at=updated_at,
    )
