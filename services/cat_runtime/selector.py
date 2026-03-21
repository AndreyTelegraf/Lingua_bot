from __future__ import annotations

from dataclasses import dataclass
from math import exp
from typing import Iterable

from services.cat_runtime.item_model import CATItemModel


@dataclass(slots=True)
class CATCandidateScore:
    item_id: int
    information: float
    distance_to_theta: float
    difficulty_b: float
    discrimination_a: float


def _sigmoid(x: float) -> float:
    if x >= 0:
        z = exp(-x)
        return 1.0 / (1.0 + z)
    z = exp(x)
    return z / (1.0 + z)


def item_information(
    item: CATItemModel,
    *,
    theta: float,
) -> float:
    a = max(float(item.discrimination_a), 1e-6)
    b = float(item.difficulty_b)
    p = _sigmoid(a * (float(theta) - b))
    p = min(max(p, 1e-6), 1.0 - 1e-6)
    return float((a * a) * p * (1.0 - p))


def rank_candidates_for_theta(
    items: Iterable[CATItemModel],
    *,
    theta: float,
    exclude_item_ids: set[int] | None = None,
) -> list[CATCandidateScore]:
    excluded = exclude_item_ids or set()
    out: list[CATCandidateScore] = []

    for item in items:
        if int(item.item_id) in excluded:
            continue
        info = item_information(item, theta=theta)
        out.append(
            CATCandidateScore(
                item_id=int(item.item_id),
                information=float(info),
                distance_to_theta=abs(float(item.difficulty_b) - float(theta)),
                difficulty_b=float(item.difficulty_b),
                discrimination_a=float(item.discrimination_a),
            )
        )

    return sorted(
        out,
        key=lambda x: (
            -x.information,
            x.distance_to_theta,
            -x.discrimination_a,
            x.item_id,
        ),
    )


def select_next_item_for_theta(
    items: Iterable[CATItemModel],
    *,
    theta: float,
    exclude_item_ids: set[int] | None = None,
) -> CATItemModel | None:
    excluded = exclude_item_ids or set()
    ranked = rank_candidates_for_theta(
        items,
        theta=theta,
        exclude_item_ids=excluded,
    )
    if not ranked:
        return None

    wanted_id = ranked[0].item_id
    for item in items:
        if int(item.item_id) == wanted_id:
            return item
    return None
