from __future__ import annotations

from dataclasses import dataclass
from math import exp, sqrt

from services.cat_runtime.item_model import CATItemModel


@dataclass(slots=True)
class CATResponse:
    item_id: int
    score: float
    difficulty_b: float
    discrimination_a: float = 1.0


@dataclass(slots=True)
class CATEstimate:
    theta: float
    se: float
    information: float
    items_answered: int
    converged: bool


def _sigmoid(x: float) -> float:
    if x >= 0:
        z = exp(-x)
        return 1.0 / (1.0 + z)
    z = exp(x)
    return z / (1.0 + z)


def estimate_theta_map(
    responses: list[CATResponse],
    *,
    prior_mean: float = 0.0,
    prior_variance: float = 1.0,
    max_iter: int = 25,
) -> CATEstimate:
    """
    Minimal CAT estimator contract for next layers.

    This is a bounded 2PL-style MAP estimator with normal prior.
    It is suitable as a contract layer and deterministic test target.
    """
    if not responses:
        return CATEstimate(
            theta=float(prior_mean),
            se=float(sqrt(prior_variance)),
            information=0.0,
            items_answered=0,
            converged=True,
        )

    theta = float(prior_mean)
    prior_precision = 1.0 / float(prior_variance)
    converged = False

    for _ in range(max_iter):
        grad = -(theta - prior_mean) * prior_precision
        hess = -prior_precision
        info_sum = 0.0

        for r in responses:
            a = max(float(r.discrimination_a), 1e-6)
            b = float(r.difficulty_b)
            y = max(0.0, min(1.0, float(r.score)))

            p = _sigmoid(a * (theta - b))
            p = min(max(p, 1e-6), 1.0 - 1e-6)

            grad += a * (y - p)
            item_info = (a * a) * p * (1.0 - p)
            hess -= item_info
            info_sum += item_info

        if abs(hess) < 1e-9:
            break

        step = grad / hess
        theta_next = theta - step
        theta_next = max(-4.0, min(4.0, theta_next))

        if abs(theta_next - theta) < 1e-4:
            theta = theta_next
            converged = True
            break

        theta = theta_next

    info_total = prior_precision
    for r in responses:
        a = max(float(r.discrimination_a), 1e-6)
        b = float(r.difficulty_b)
        p = _sigmoid(a * (theta - b))
        p = min(max(p, 1e-6), 1.0 - 1e-6)
        info_total += (a * a) * p * (1.0 - p)

    se = 1.0 / sqrt(max(info_total, 1e-9))

    return CATEstimate(
        theta=float(theta),
        se=float(se),
        information=float(max(info_total - prior_precision, 0.0)),
        items_answered=len(responses),
        converged=converged,
    )


def build_cat_responses(
    rows: list[tuple[int, float, float, float | None]],
) -> list[CATResponse]:
    out: list[CATResponse] = []
    for item_id, score, difficulty_b, discrimination_a in rows:
        out.append(
            CATResponse(
                item_id=int(item_id),
                score=float(score),
                difficulty_b=float(difficulty_b),
                discrimination_a=1.0 if discrimination_a is None else float(discrimination_a),
            )
        )
    return out


def estimate_from_items(
    items: list[CATItemModel],
    *,
    correctness: list[float],
) -> CATEstimate:
    if len(items) != len(correctness):
        raise ValueError("items and correctness must have the same length")

    responses = [
        CATResponse(
            item_id=int(item.item_id),
            score=float(score),
            difficulty_b=float(item.difficulty_b),
            discrimination_a=float(item.discrimination_a),
        )
        for item, score in zip(items, correctness)
    ]
    return estimate_theta_map(responses)
