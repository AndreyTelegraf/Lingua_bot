from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any


VOCAB_SPEC_VERSION = "vocab_v2"
VOCAB_SCORING_VERSION = "vocab_scoring_v2"
VOCAB_FRESH_UNTIL_DAYS = 90


@dataclass(slots=True)
class BehavioralFlags:
    dont_know_rate: float | None = None
    fast_answer_rate: float | None = None
    slow_answer_rate: float | None = None


@dataclass(slots=True)
class VocabResultSnapshot:
    mode: str
    spec_version: str
    scoring_version: str
    product_band: str
    range_min: int
    range_max: int
    correct_count: int
    total_questions: int
    confidence: str
    fresh_until_days: int
    prior_bucket: str
    prior_theta_hint: float
    behavioral_flags: dict[str, float | None]
    generated_at: str

    def to_json_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json_text(self) -> str:
        return json.dumps(self.to_json_dict(), ensure_ascii=False, separators=(",", ":"))


@dataclass(slots=True)
class LatestVocabPrior:
    attempt_id: int | str
    finished_at: str
    snapshot: dict[str, Any]
    is_usable_as_level_prior: bool

    def to_json_dict(self) -> dict[str, Any]:
        return asdict(self)


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def map_range_to_product_band(*, range_min: int, range_max: int) -> str:
    upper = range_max

    if upper < 500:
        return "A0"
    if upper <= 1000:
        return "A1"
    if upper <= 1500:
        return "A1+"
    if upper <= 2500:
        return "A2"
    if upper <= 4000:
        return "B1"
    if upper <= 6500:
        return "B2"
    if upper <= 8000:
        return "C1"
    return "C1+"


def map_band_to_prior_bucket(product_band: str) -> str:
    mapping = {
        "A0": "a0",
        "A1": "a1",
        "A1+": "a1p",
        "A2": "a2",
        "B1": "b1",
        "B2": "b2",
        "C1": "c1",
        "C1+": "c1p",
    }
    try:
        return mapping[product_band]
    except KeyError as exc:
        raise ValueError(f"Unsupported product_band: {product_band}") from exc


def map_band_to_prior_theta_hint(product_band: str) -> float:
    mapping = {
        "A0": -2.0,
        "A1": -1.4,
        "A1+": -1.0,
        "A2": -0.4,
        "B1": 0.2,
        "B2": 0.9,
        "C1": 1.5,
        "C1+": 2.0,
    }
    try:
        return mapping[product_band]
    except KeyError as exc:
        raise ValueError(f"Unsupported product_band: {product_band}") from exc


def infer_confidence(
    *,
    correct_count: int,
    total_questions: int,
    dont_know_rate: float | None = None,
    fast_answer_rate: float | None = None,
    slow_answer_rate: float | None = None,
    is_complete: bool = True,
) -> str:
    if not is_complete or total_questions <= 0:
        return "low"

    if dont_know_rate is not None and dont_know_rate >= 0.75:
        return "low"

    if fast_answer_rate is not None and fast_answer_rate >= 0.85:
        return "low"

    if (
        fast_answer_rate is not None
        and slow_answer_rate is not None
        and fast_answer_rate <= 0.20
        and slow_answer_rate <= 0.25
        and 0 < correct_count < total_questions
    ):
        return "high"

    return "medium"


def build_vocab_result_snapshot(
    *,
    range_min: int,
    range_max: int,
    correct_count: int,
    total_questions: int,
    confidence: str | None = None,
    dont_know_rate: float | None = None,
    fast_answer_rate: float | None = None,
    slow_answer_rate: float | None = None,
    generated_at: str | None = None,
) -> VocabResultSnapshot:
    product_band = map_range_to_product_band(range_min=range_min, range_max=range_max)
    if confidence is None:
        confidence = infer_confidence(
            correct_count=correct_count,
            total_questions=total_questions,
            dont_know_rate=dont_know_rate,
            fast_answer_rate=fast_answer_rate,
            slow_answer_rate=slow_answer_rate,
            is_complete=True,
        )

    return VocabResultSnapshot(
        mode="vocab",
        spec_version=VOCAB_SPEC_VERSION,
        scoring_version=VOCAB_SCORING_VERSION,
        product_band=product_band,
        range_min=range_min,
        range_max=range_max,
        correct_count=correct_count,
        total_questions=total_questions,
        confidence=confidence,
        fresh_until_days=VOCAB_FRESH_UNTIL_DAYS,
        prior_bucket=map_band_to_prior_bucket(product_band),
        prior_theta_hint=map_band_to_prior_theta_hint(product_band),
        behavioral_flags=asdict(
            BehavioralFlags(
                dont_know_rate=dont_know_rate,
                fast_answer_rate=fast_answer_rate,
                slow_answer_rate=slow_answer_rate,
            )
        ),
        generated_at=generated_at or utc_now_iso(),
    )


def parse_snapshot_text(raw: str) -> dict[str, Any]:
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("Snapshot must decode to dict")
    return data


def compute_is_usable_as_level_prior(
    *,
    finished_at_iso: str,
    fresh_until_days: int,
    now_utc: datetime | None = None,
) -> bool:
    now_utc = now_utc or datetime.now(UTC)

    finished_at = datetime.fromisoformat(finished_at_iso.replace("Z", "+00:00"))
    if finished_at.tzinfo is None:
        finished_at = finished_at.replace(tzinfo=UTC)

    age_days = (now_utc - finished_at).days
    return age_days <= fresh_until_days
