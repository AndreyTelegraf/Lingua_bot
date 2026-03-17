from __future__ import annotations

import sqlite3
from typing import Any


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    try:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    except Exception:
        return set()
    return {str(r[1]) for r in rows}


def _fetch_answer_rows(conn: sqlite3.Connection, *, attempt_id: int) -> list[dict[str, Any]]:
    answer_cols = _table_columns(conn, "vocab_answers")
    item_cols = _table_columns(conn, "vocab_items")

    has_is_correct = "is_correct" in answer_cols
    has_concept = "concept_group" in item_cols
    has_cefr = "cefr_estimate" in item_cols
    has_lemma = "lemma" in item_cols
    has_pos = "pos" in item_cols
    has_freq = "freq_rank" in item_cols
    has_correct_answer = "correct_answer" in item_cols

    q = f"""
    SELECT
      va.item_id AS item_id,
      {"COALESCE(va.is_correct, 0)" if has_is_correct else "0"} AS is_correct,
      { "vi.lemma" if has_lemma else "NULL" } AS lemma,
      { "vi.pos" if has_pos else "NULL" } AS pos,
      { "vi.cefr_estimate" if has_cefr else "NULL" } AS cefr_estimate,
      { "vi.concept_group" if has_concept else "NULL" } AS concept_group,
      { "vi.freq_rank" if has_freq else "NULL" } AS freq_rank,
      { "vi.correct_answer" if has_correct_answer else "NULL" } AS correct_answer
    FROM vocab_answers va
    LEFT JOIN vocab_items vi ON vi.id = va.item_id
    WHERE va.attempt_id = ?
    ORDER BY va.id
    """
    rows = conn.execute(q, (attempt_id,)).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "item_id": r["item_id"],
                "is_correct": int(r["is_correct"] or 0),
                "lemma": r["lemma"],
                "pos": r["pos"],
                "cefr_estimate": r["cefr_estimate"],
                "concept_group": r["concept_group"],
                "freq_rank": r["freq_rank"],
                "correct_answer": r["correct_answer"],
            }
        )
    return out


def _count_map(rows: list[dict[str, Any]], key: str, *, meaningful_concept_only: bool = False) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in rows:
        v = r.get(key)
        if not v:
            continue
        if meaningful_concept_only and key == "concept_group":
            if r.get("lemma") and v == r.get("lemma"):
                continue
        out[str(v)] = out.get(str(v), 0) + 1
    return dict(sorted(out.items(), key=lambda kv: (-kv[1], kv[0])))


def _bank_active_counts(conn: sqlite3.Connection, column: str, *, meaningful_concept_only: bool = False) -> dict[str, int]:
    item_cols = _table_columns(conn, "vocab_items")
    if column not in item_cols:
        return {}

    q = f"SELECT {column} AS v, lemma FROM vocab_items WHERE is_active = 1"
    rows = conn.execute(q).fetchall()
    out: dict[str, int] = {}
    for r in rows:
        v = r["v"]
        if not v:
            continue
        if meaningful_concept_only and column == "concept_group":
            lemma = r["lemma"]
            if lemma and v == lemma:
                continue
        out[str(v)] = out.get(str(v), 0) + 1
    return dict(sorted(out.items(), key=lambda kv: (-kv[1], kv[0])))


def _accuracy_by(rows: list[dict[str, Any]], key: str, *, meaningful_concept_only: bool = False) -> list[dict[str, Any]]:
    agg: dict[str, dict[str, int]] = {}
    for r in rows:
        v = r.get(key)
        if not v:
            continue
        if meaningful_concept_only and key == "concept_group":
            if r.get("lemma") and v == r.get("lemma"):
                continue
        bucket = agg.setdefault(str(v), {"correct": 0, "total": 0})
        bucket["total"] += 1
        bucket["correct"] += int(r.get("is_correct") or 0)

    ranked = []
    for k, v in agg.items():
        ranked.append(
            {
                "key": k,
                "correct": v["correct"],
                "total": v["total"],
                "accuracy": round(v["correct"] / v["total"], 4) if v["total"] else 0.0,
            }
        )
    ranked.sort(key=lambda x: (-x["accuracy"], -x["total"], x["key"]))
    return ranked


def _weak_rank(rows: list[dict[str, Any]], key: str, *, meaningful_concept_only: bool = False) -> list[dict[str, Any]]:
    ranked = _accuracy_by(rows, key, meaningful_concept_only=meaningful_concept_only)
    ranked.sort(key=lambda x: (x["accuracy"], -x["total"], x["key"]))
    return ranked


def _baseline_band(correct_ratio: float) -> str:
    if correct_ratio < 0.20:
        return "A1"
    if correct_ratio < 0.35:
        return "A2"
    if correct_ratio < 0.50:
        return "B1"
    if correct_ratio < 0.65:
        return "B2"
    if correct_ratio < 0.80:
        return "C1"
    return "C2"


def build_profile(conn: sqlite3.Connection, *, attempt_id: int) -> dict[str, Any]:
    rows = _fetch_answer_rows(conn, attempt_id=attempt_id)
    answered_total = len(rows)
    correct_total = sum(int(r["is_correct"]) for r in rows)
    ratio = (correct_total / answered_total) if answered_total else 0.0

    observed_pos = _count_map(rows, "pos")
    observed_cefr = _count_map(rows, "cefr_estimate")
    observed_cg = _count_map(rows, "concept_group", meaningful_concept_only=True)

    bank_pos = _bank_active_counts(conn, "pos")
    bank_cefr = _bank_active_counts(conn, "cefr_estimate")
    bank_cg = _bank_active_counts(conn, "concept_group", meaningful_concept_only=True)

    strongest_pos = _accuracy_by(rows, "pos")
    weakest_pos = _weak_rank(rows, "pos")
    if len(strongest_pos) <= 1:
        strongest_pos = []
        weakest_pos = []

    strongest_cefr = _accuracy_by(rows, "cefr_estimate")
    weakest_cefr = _weak_rank(rows, "cefr_estimate")

    strongest_cg = _accuracy_by(rows, "concept_group", meaningful_concept_only=True)
    weakest_cg = _weak_rank(rows, "concept_group", meaningful_concept_only=True)

    known = [
        {
            "lemma": r["lemma"],
            "pos": r["pos"],
            "cefr_estimate": r["cefr_estimate"],
            "concept_group": (None if r["concept_group"] == r["lemma"] else r["concept_group"]),
            "freq_rank": r["freq_rank"],
            "correct_answer": r["correct_answer"],
            "is_correct": r["is_correct"],
        }
        for r in rows if int(r["is_correct"]) == 1
    ][:15]

    weak = [
        {
            "lemma": r["lemma"],
            "pos": r["pos"],
            "cefr_estimate": r["cefr_estimate"],
            "concept_group": (None if r["concept_group"] == r["lemma"] else r["concept_group"]),
            "freq_rank": r["freq_rank"],
            "correct_answer": r["correct_answer"],
            "is_correct": r["is_correct"],
        }
        for r in rows if int(r["is_correct"]) == 0
    ][:15]

    meaningful_support = sum(observed_cg.values())
    lesson_packs = [x["key"] for x in weakest_cg if x["total"] >= 2 and x["accuracy"] < 0.5][:3]
    game_packs = [x["key"] for x in weakest_pos if x["total"] >= 2 and x["accuracy"] < 0.5][:2]

    return {
        "attempt_id": attempt_id,
        "lexical_baseline": {
            "estimated_vocab_size_band": _baseline_band(ratio) if answered_total else None,
            "confidence": "medium" if answered_total >= 12 else "low",
            "correctness_ratio": round(ratio, 4) if answered_total else None,
            "correct_count": correct_total,
            "total_questions": answered_total,
        },
        "observed_attempt_profile": {
            "pos_counts": observed_pos,
            "cefr_counts": observed_cefr,
            "meaningful_concept_group_counts": observed_cg,
        },
        "bank_baseline_profile": {
            "active_pos_counts": bank_pos,
            "active_cefr_counts": bank_cefr,
            "active_meaningful_concept_group_counts": bank_cg,
        },
        "lexical_profile": {
            "strongest_pos": strongest_pos,
            "weakest_pos": weakest_pos,
            "strongest_cefr": strongest_cefr,
            "weakest_cefr": weakest_cefr,
            "strongest_concept_groups": strongest_cg,
            "weak_concept_groups": weakest_cg,
            "known_lemmas_sample": known,
            "weak_lemmas_sample": weak,
        },
        "progression_ready_hints": {
            "recommended_lesson_packs": lesson_packs if meaningful_support >= 2 else [],
            "recommended_game_packs": game_packs if len(observed_pos) >= 2 else [],
            "ready_for_level_focus": ratio >= 0.30 if answered_total else False,
            "ready_for_ciple_focus": ratio >= 0.55 if answered_total else False,
        },
        "signal_quality": {
            "single_pos_attempt": len(observed_pos) <= 1,
            "meaningful_concept_group_support_total": meaningful_support,
            "recommended_lesson_packs_confident": meaningful_support >= 2,
            "recommended_game_packs_confident": len(observed_pos) >= 2,
        },
        "notes": [
            "Stable progression export profile for vocab.",
            "Meaningful concept groups exclude fallback concept_group=lemma.",
        ],
    }


def build_vocab_progression_export(
    conn: sqlite3.Connection,
    *,
    attempt_id: int,
) -> dict[str, Any]:
    return {
        "mode": "vocab",
        "spec_version": "progression_export_v1",
        "attempt_id": attempt_id,
        "profile": build_profile(conn, attempt_id=attempt_id),
    }
