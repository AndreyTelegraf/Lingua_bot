from __future__ import annotations

from tools.build_community_replenishment_wave_v1 import analyze, build_wave, is_semantically_valid


def test_wave_respects_size_and_family_caps() -> None:
    items = build_wave(target_size=16, max_per_family=2, min_families=8, seed=42)
    assert len(items) == 16

    family_counts: dict[str, int] = {}
    for item in items:
        family_counts[item.opening_family] = family_counts.get(item.opening_family, 0) + 1

    assert max(family_counts.values()) <= 2
    assert len(family_counts) >= 8


def test_wave_passes_internal_diversity_gate() -> None:
    items = build_wave(target_size=16, max_per_family=2, min_families=8, seed=42)
    report = analyze(items)

    assert len(items) == 16
    assert report["passed"] is True
    assert report["violations"] == []


def test_wave_spreads_topics_and_formats() -> None:
    items = build_wave(target_size=16, max_per_family=2, min_families=8, seed=42)
    report = analyze(items)

    assert len(report["topics"]) >= 6
    assert len(report["formats"]) == 3


def test_no_prefix_bucket_collapses() -> None:
    items = build_wave(target_size=16, max_per_family=2, min_families=8, seed=42)
    report = analyze(items)

    assert max(report["first1"].values()) <= 4
    assert max(report["first2"].values()) <= 4
    assert max(report["first3"].values()) <= 3


def test_all_pairs_are_semantically_valid() -> None:
    items = build_wave(target_size=16, max_per_family=2, min_families=8, seed=42)
    assert items
    assert all(is_semantically_valid(item.context, item.intent) for item in items)
