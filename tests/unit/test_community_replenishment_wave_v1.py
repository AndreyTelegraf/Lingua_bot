from __future__ import annotations

from pathlib import Path

from tools.build_community_replenishment_wave_v1 import (
    analyze,
    build_wave,
    load_scenarios,
)

SCENARIO_PACK = Path("data/community_authoring/scenario_pack_v1.json")


def test_scenario_pack_loads() -> None:
    scenarios = load_scenarios(SCENARIO_PACK)
    assert len(scenarios) >= 12
    assert all(s.scenario_id for s in scenarios)
    assert all(s.question_forms for s in scenarios)


def test_wave_respects_size_and_unique_scenarios() -> None:
    items = build_wave(
        target_size=12,
        max_per_opening=2,
        min_openings=8,
        seed=42,
        scenario_pack_path=SCENARIO_PACK,
    )
    assert len(items) == 12
    assert len({item.scenario_id for item in items}) == 12


def test_wave_passes_internal_gate() -> None:
    items = build_wave(
        target_size=12,
        max_per_opening=2,
        min_openings=8,
        seed=42,
        scenario_pack_path=SCENARIO_PACK,
    )
    report = analyze(items)
    assert report["passed"] is True
    assert report["violations"] == []


def test_no_prefix_bucket_collapses() -> None:
    items = build_wave(
        target_size=12,
        max_per_opening=2,
        min_openings=8,
        seed=42,
        scenario_pack_path=SCENARIO_PACK,
    )
    report = analyze(items)
    assert max(report["first1"].values()) <= 3
    assert max(report["first2"].values()) <= 3
    assert max(report["first3"].values()) <= 2


def test_opening_diversity_floor_holds() -> None:
    items = build_wave(
        target_size=12,
        max_per_opening=2,
        min_openings=8,
        seed=42,
        scenario_pack_path=SCENARIO_PACK,
    )
    assert len({item.opening_family for item in items}) >= 8


def test_no_awkward_meta_stems_in_output() -> None:
    items = build_wave(
        target_size=12,
        max_per_opening=2,
        min_openings=8,
        seed=42,
        scenario_pack_path=SCENARIO_PACK,
    )
    texts = [item.text.lower() for item in items]
    banned = (
        "как по-португальски",
        "как бы вы",
        "буквально перевести",
        "официально спросить",
        "как обычно называют на почте, чтобы",
        "когда уместно сказать в finanças, чтобы",
    )
    assert not any(any(stem in text for stem in banned) for text in texts)


def test_no_punctuation_artifacts_in_output() -> None:
    items = build_wave(
        target_size=12,
        max_per_opening=2,
        min_openings=8,
        seed=42,
        scenario_pack_path=SCENARIO_PACK,
    )
    texts = [item.text for item in items]
    assert not any(".," in text or "., " in text for text in texts)
