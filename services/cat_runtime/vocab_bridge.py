from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from .item_model import CATItemModel
from .runtime import (
    CATStartResult,
    answer_cat_session_runtime,
    load_cat_session_runtime,
    start_cat_session_runtime,
)


@dataclass(slots=True)
class CATBridgeDecision:
    enabled: bool
    reason: str | None
    mode: str
    source: str


def cat_feature_enabled(flag_value: Any) -> bool:
    raw = str(flag_value or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def should_use_cat_for_mode(
    *,
    mode: str,
    feature_enabled: bool,
    supported_modes: set[str] | None = None,
) -> CATBridgeDecision:
    mode_norm = str(mode or "").strip().lower()
    supported = supported_modes or {"vocab"}

    if not feature_enabled:
        return CATBridgeDecision(
            enabled=False,
            reason="feature_disabled",
            mode=mode_norm,
            source="flag",
        )

    if mode_norm not in supported:
        return CATBridgeDecision(
            enabled=False,
            reason="mode_not_supported",
            mode=mode_norm,
            source="policy",
        )

    return CATBridgeDecision(
        enabled=True,
        reason=None,
        mode=mode_norm,
        source="policy",
    )


def build_cat_session_id(
    *,
    user_id: int,
    mode: str,
    attempt_id: int | None = None,
) -> str:
    mode_norm = str(mode or "").strip().lower() or "unknown"
    if attempt_id is not None:
        return f"cat:{mode_norm}:u{int(user_id)}:a{int(attempt_id)}"
    return f"cat:{mode_norm}:u{int(user_id)}"


def start_mode_cat_bridge(
    conn,
    *,
    user_id: int,
    mode: str,
    feature_enabled: bool,
    item_bank: Sequence[CATItemModel] | None = None,
    attempt_id: int | None = None,
    started_at: str | None = None,
    metadata: dict[str, Any] | None = None,
    active_only: bool = True,
    limit: int | None = None,
) -> CATStartResult | None:
    decision = should_use_cat_for_mode(
        mode=mode,
        feature_enabled=feature_enabled,
    )
    if not decision.enabled:
        return None

    session_id = build_cat_session_id(
        user_id=user_id,
        mode=mode,
        attempt_id=attempt_id,
    )

    payload = dict(metadata or {})
    payload.setdefault("bridge_mode", str(mode))
    if attempt_id is not None:
        payload.setdefault("attempt_id", int(attempt_id))

    return start_cat_session_runtime(
        conn,
        session_id=session_id,
        user_id=int(user_id),
        modality=str(mode),
        item_bank=item_bank,
        started_at=started_at,
        metadata=payload,
        active_only=active_only,
        limit=limit,
    )


def answer_mode_cat_bridge(
    conn,
    *,
    user_id: int,
    mode: str,
    item: CATItemModel,
    response_value: int | float,
    is_correct: bool,
    item_bank: Sequence[CATItemModel] | None = None,
    attempt_id: int | None = None,
    updated_at: str | None = None,
):
    session_id = build_cat_session_id(
        user_id=user_id,
        mode=mode,
        attempt_id=attempt_id,
    )
    session = load_cat_session_runtime(conn, session_id=session_id)
    if session is None:
        raise ValueError("cat bridge session not found")

    return answer_cat_session_runtime(
        conn,
        session_id=session_id,
        item=item,
        response_value=response_value,
        is_correct=is_correct,
        item_bank=item_bank,
        updated_at=updated_at,
    )
