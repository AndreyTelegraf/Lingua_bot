from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .estimator import CATEstimate
from .item_model import CATItemModel


@dataclass(slots=True)
class CATSessionAnswer:
    item_id: int
    response_value: int
    is_correct: bool
    theta_before: float | None = None
    theta_after: float | None = None
    se_before: float | None = None
    se_after: float | None = None


@dataclass(slots=True)
class CATSessionState:
    session_id: str
    user_id: int | None
    modality: str
    items_administered: list[int] = field(default_factory=list)
    answers: list[CATSessionAnswer] = field(default_factory=list)
    theta: float = 0.0
    se: float | None = None
    started_at: str | None = None
    updated_at: str | None = None
    status: str = "in_progress"
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def questions_answered(self) -> int:
        return len(self.answers)


def create_cat_session(
    *,
    session_id: str,
    user_id: int | None,
    modality: str,
    theta: float = 0.0,
    se: float | None = None,
    started_at: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> CATSessionState:
    return CATSessionState(
        session_id=session_id,
        user_id=user_id,
        modality=modality,
        theta=float(theta),
        se=None if se is None else float(se),
        started_at=started_at,
        updated_at=started_at,
        metadata=dict(metadata or {}),
    )


def append_answer(
    state: CATSessionState,
    *,
    item: CATItemModel,
    response_value: int,
    is_correct: bool,
    estimate_after: CATEstimate | None = None,
    updated_at: str | None = None,
) -> CATSessionState:
    item_id = int(item.item_id)
    if item_id in state.items_administered:
        raise ValueError("item already administered in this session")

    ans = CATSessionAnswer(
        item_id=item_id,
        response_value=int(response_value),
        is_correct=bool(is_correct),
        theta_before=float(state.theta),
        theta_after=None if estimate_after is None else float(estimate_after.theta),
        se_before=None if state.se is None else float(state.se),
        se_after=None if estimate_after is None or estimate_after.se is None else float(estimate_after.se),
    )

    state.items_administered.append(item_id)
    state.answers.append(ans)

    if estimate_after is not None:
        state.theta = float(estimate_after.theta)
        state.se = None if estimate_after.se is None else float(estimate_after.se)

    if updated_at is not None:
        state.updated_at = updated_at

    return state


def finish_cat_session(
    state: CATSessionState,
    *,
    final_estimate: CATEstimate | None = None,
    finished_at: str | None = None,
    reason: str | None = None,
) -> CATSessionState:
    if final_estimate is not None:
        state.theta = float(final_estimate.theta)
        state.se = None if final_estimate.se is None else float(final_estimate.se)

    state.status = "finished"
    state.updated_at = finished_at
    if reason is not None:
        state.metadata["finish_reason"] = reason
    return state


def serialize_cat_session(state: CATSessionState) -> dict[str, Any]:
    return {
        "session_id": state.session_id,
        "user_id": state.user_id,
        "modality": state.modality,
        "items_administered": list(state.items_administered),
        "answers": [
            {
                "item_id": a.item_id,
                "response_value": a.response_value,
                "is_correct": a.is_correct,
                "theta_before": a.theta_before,
                "theta_after": a.theta_after,
                "se_before": a.se_before,
                "se_after": a.se_after,
            }
            for a in state.answers
        ],
        "theta": state.theta,
        "se": state.se,
        "started_at": state.started_at,
        "updated_at": state.updated_at,
        "status": state.status,
        "metadata": dict(state.metadata),
        "questions_answered": state.questions_answered,
    }


def restore_cat_session(payload: dict[str, Any]) -> CATSessionState:
    state = CATSessionState(
        session_id=str(payload["session_id"]),
        user_id=None if payload.get("user_id") is None else int(payload["user_id"]),
        modality=str(payload["modality"]),
        items_administered=[int(x) for x in payload.get("items_administered", [])],
        theta=float(payload.get("theta", 0.0)),
        se=None if payload.get("se") is None else float(payload["se"]),
        started_at=payload.get("started_at"),
        updated_at=payload.get("updated_at"),
        status=str(payload.get("status", "in_progress")),
        metadata=dict(payload.get("metadata", {})),
    )
    for raw in payload.get("answers", []):
        state.answers.append(
            CATSessionAnswer(
                item_id=int(raw["item_id"]),
                response_value=int(raw["response_value"]),
                is_correct=bool(raw["is_correct"]),
                theta_before=None if raw.get("theta_before") is None else float(raw["theta_before"]),
                theta_after=None if raw.get("theta_after") is None else float(raw["theta_after"]),
                se_before=None if raw.get("se_before") is None else float(raw["se_before"]),
                se_after=None if raw.get("se_after") is None else float(raw["se_after"]),
            )
        )
    return state
