from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from .item_model import CATItemModel
from .vocab_bridge import should_use_cat_for_mode
from .vocab_handoff import CATVocabHandoff, build_vocab_cat_handoff, start_vocab_cat_handoff


@dataclass(slots=True)
class CATVocabEntryDecision:
    use_cat: bool
    reason: str | None
    mode: str
    handoff: CATVocabHandoff | None


@dataclass(slots=True)
class CATVocabEntryStartResult:
    decision: CATVocabEntryDecision
    cat_started: Any | None


def decide_vocab_cat_entry(
    *,
    user_id: int,
    attempt_id: int,
    mode: str = "vocab",
    feature_enabled: bool,
    metadata: dict[str, Any] | None = None,
) -> CATVocabEntryDecision:
    bridge = should_use_cat_for_mode(
        mode=mode,
        feature_enabled=feature_enabled,
    )
    if not bridge.enabled:
        return CATVocabEntryDecision(
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
    return CATVocabEntryDecision(
        use_cat=True,
        reason=None,
        mode=str(mode),
        handoff=handoff,
    )


def start_vocab_runtime_cat_entry(
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
) -> CATVocabEntryStartResult:
    decision = decide_vocab_cat_entry(
        user_id=int(user_id),
        attempt_id=int(attempt_id),
        mode=str(mode),
        feature_enabled=feature_enabled,
        metadata=metadata,
    )

    if not decision.use_cat:
        return CATVocabEntryStartResult(
            decision=decision,
            cat_started=None,
        )

    started = start_vocab_cat_handoff(
        conn,
        user_id=int(user_id),
        attempt_id=int(attempt_id),
        feature_enabled=feature_enabled,
        item_bank=item_bank,
        started_at=started_at,
        metadata=metadata,
        active_only=active_only,
        limit=limit,
    )
    return CATVocabEntryStartResult(
        decision=decision,
        cat_started=started,
    )
