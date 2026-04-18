"""
Unit tests for scripts/noun10k_tranche2_prepare.py.

Uses in-memory SQLite fixtures and a minimal CSV string.
Does NOT touch data/lingua_staging.db. No DB writes.
"""
from __future__ import annotations

import csv
import io
import sqlite3
import tempfile
import os

import pytest

from scripts.noun10k_tranche2_prepare import (
    build_tranche2_pack,
    check_duplicate_lemma,
    check_rule1a,
    check_rule1b,
    load_active_bank,
    select_tranche2,
    write_apply_script_donotrun,
    write_manifest_csv,
    write_manifest_json,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE vocab_items (
            id INTEGER PRIMARY KEY,
            lemma TEXT NOT NULL,
            pos TEXT NOT NULL DEFAULT 'noun',
            bin_name TEXT NOT NULL DEFAULT '10K',
            correct_answer TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE vocab_choices (
            id INTEGER PRIMARY KEY,
            item_id INTEGER NOT NULL,
            choice_text TEXT NOT NULL,
            is_correct INTEGER NOT NULL DEFAULT 0
        );
        """
    )
    return conn


def _add_item(conn, item_id, lemma, correct_answer, is_active=0, pos="noun", bin_name="10K"):
    conn.execute(
        "INSERT INTO vocab_items (id, lemma, pos, bin_name, correct_answer, is_active) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (item_id, lemma, pos, bin_name, correct_answer, is_active),
    )
    conn.commit()


def _add_choices(conn, item_id, correct_text, distractor_texts):
    next_id = conn.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM vocab_choices").fetchone()[0]
    conn.execute(
        "INSERT INTO vocab_choices (id, item_id, choice_text, is_correct) VALUES (?, ?, ?, 1)",
        (next_id, item_id, correct_text),
    )
    for i, d in enumerate(distractor_texts):
        conn.execute(
            "INSERT INTO vocab_choices (id, item_id, choice_text, is_correct) VALUES (?, ?, ?, 0)",
            (next_id + i + 1, item_id, d),
        )
    conn.commit()


def _csv_string(rows: list[dict]) -> str:
    fields = [
        "candidate_id", "lemma", "pos", "bin_name", "cefr_target",
        "correct_answer", "distractor_1", "distractor_2", "distractor_3",
        "judge_note", "import_status", "import_item_id",
        "concept_group", "topic_tag", "collision_note",
    ]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields)
    writer.writeheader()
    for r in rows:
        writer.writerow(r)
    return buf.getvalue()


def _make_ready_row(candidate_id, lemma, correct_answer, distractors, item_id, concept_group="misc", collision_note="CLEAN"):
    d1, d2, d3 = distractors
    return {
        "candidate_id": candidate_id,
        "lemma": lemma,
        "pos": "noun",
        "bin_name": "10K",
        "cefr_target": "B2",
        "correct_answer": correct_answer,
        "distractor_1": d1,
        "distractor_2": d2,
        "distractor_3": d3,
        "judge_note": "test",
        "import_status": "READY",
        "import_item_id": str(item_id),
        "concept_group": concept_group,
        "topic_tag": "test",
        "collision_note": collision_note,
    }


# ---------------------------------------------------------------------------
# load_active_bank
# ---------------------------------------------------------------------------


def test_load_active_bank_collects_cas_and_distractors():
    conn = _make_db()
    _add_item(conn, 1, "palavra", "слово", is_active=1)
    _add_choices(conn, 1, "слово", ["буква", "фраза", "текст"])

    bank = load_active_bank(conn)
    assert "слово" in bank["active_cas"]
    assert bank["active_cas"]["слово"] == 1
    assert "буква" in bank["active_distractors"]
    assert 1 in bank["active_distractors"]["буква"]
    assert bank["active_item_count"] == 1


def test_load_active_bank_ignores_inactive():
    conn = _make_db()
    _add_item(conn, 1, "palavra", "слово", is_active=0)
    _add_choices(conn, 1, "слово", ["буква", "фраза", "текст"])

    bank = load_active_bank(conn)
    assert "слово" not in bank["active_cas"]
    assert bank["active_item_count"] == 0


# ---------------------------------------------------------------------------
# check_rule1a
# ---------------------------------------------------------------------------


def test_rule1a_passes_when_ca_not_in_active_distractors():
    bank = {"active_distractors": {"буква": [1], "фраза": [1]}}
    candidate = {"correct_answer": "слово"}
    result = check_rule1a(candidate, bank)
    assert result["passes"] is True


def test_rule1a_fails_when_ca_in_active_distractors():
    bank = {"active_distractors": {"слово": [1]}}
    candidate = {"correct_answer": "слово"}
    result = check_rule1a(candidate, bank)
    assert result["passes"] is False
    assert "слово" in result["violation"]


# ---------------------------------------------------------------------------
# check_rule1b
# ---------------------------------------------------------------------------


def test_rule1b_passes_when_no_active_ca_in_distractors():
    bank = {"active_cas": {"слово": 1, "буква": 2}}
    candidate = {"distractor_1": "тест", "distractor_2": "проба", "distractor_3": "образец"}
    result = check_rule1b(candidate, bank)
    assert result["passes"] is True


def test_rule1b_fails_when_active_ca_is_distractor():
    bank = {"active_cas": {"слово": 1}}
    candidate = {"distractor_1": "слово", "distractor_2": "тест", "distractor_3": "проба"}
    result = check_rule1b(candidate, bank)
    assert result["passes"] is False
    assert len(result["violations"]) == 1
    assert "слово" in result["violations"][0]


# ---------------------------------------------------------------------------
# check_duplicate_lemma
# ---------------------------------------------------------------------------


def test_duplicate_lemma_fails_if_active():
    conn = _make_db()
    _add_item(conn, 1, "cão", "пёс", is_active=1)
    candidate = {"lemma": "cão"}
    result = check_duplicate_lemma(candidate, conn)
    assert result["passes"] is False


def test_duplicate_lemma_passes_if_inactive():
    conn = _make_db()
    _add_item(conn, 1, "cão", "пёс", is_active=0)
    candidate = {"lemma": "cão"}
    result = check_duplicate_lemma(candidate, conn)
    assert result["passes"] is True


# ---------------------------------------------------------------------------
# select_tranche2
# ---------------------------------------------------------------------------


def _make_collision_result(item_id, eligible=True, concept_group="misc"):
    return {
        "item_id": item_id,
        "lemma": f"lemma_{item_id}",
        "eligible": eligible,
        "concept_group": concept_group,
    }


def test_select_respects_tranche_size():
    candidates = [
        _make_ready_row(f"G{i:03}", f"word_{i}", f"ca_{i}", ["d1", "d2", "d3"], 100 + i, f"group_{i}")
        for i in range(20)
    ]
    collision_results = [_make_collision_result(100 + i, eligible=True, concept_group=f"group_{i}") for i in range(20)]
    selected = select_tranche2(candidates, collision_results)
    assert len(selected) == 10


def test_select_excludes_ineligible():
    candidates = [
        _make_ready_row(f"G{i:03}", f"word_{i}", f"ca_{i}", ["d1", "d2", "d3"], 100 + i, "misc")
        for i in range(5)
    ]
    collision_results = [
        _make_collision_result(100 + i, eligible=(i != 2), concept_group="misc_" + str(i))
        for i in range(5)
    ]
    selected = select_tranche2(candidates, collision_results)
    selected_ids = {int(r["import_item_id"]) for r in selected}
    assert 102 not in selected_ids


def test_select_respects_concept_group_cap():
    candidates = [
        _make_ready_row(f"G{i:03}", f"word_{i}", f"ca_{i}", ["d1", "d2", "d3"], 100 + i, "same_group")
        for i in range(10)
    ]
    collision_results = [_make_collision_result(100 + i, eligible=True, concept_group="same_group") for i in range(10)]
    selected = select_tranche2(candidates, collision_results)
    assert len(selected) == 2


def test_select_no_intra_cluster_pair():
    # WARN items with mutual distractor cross-dependency.
    # CLEAN items are guaranteed to have no such conflicts (items with
    # mutual cross-use are always marked WARN in the collision_note).
    # The conflict avoidance algorithm applies to the WARN path.
    candidates = [
        _make_ready_row("G001", "word_a", "alpha", ["beta", "gamma", "delta"], 101, "cluster",
                        collision_note="WARN: beta is CA of G002"),
        _make_ready_row("G002", "word_b", "beta", ["alpha", "gamma", "delta"], 102, "cluster2",
                        collision_note="WARN: alpha is CA of G001"),
    ]
    collision_results = [
        _make_collision_result(101, eligible=True, concept_group="cluster"),
        _make_collision_result(102, eligible=True, concept_group="cluster2"),
    ]
    selected = select_tranche2(candidates, collision_results)
    selected_ids = {int(r["import_item_id"]) for r in selected}
    # G001 is processed first and added. G002's d1="alpha" is G001's CA → conflict → G002 skipped.
    assert not (101 in selected_ids and 102 in selected_ids), (
        "Both WARN items from an intra-cluster pair must not be selected together"
    )


# ---------------------------------------------------------------------------
# build_tranche2_pack integration
# ---------------------------------------------------------------------------


def test_build_pack_hard_blocks_rule1b_violations():
    conn = _make_db()
    # Active item with CA "активный"
    _add_item(conn, 1, "active_word", "активный", is_active=1)
    _add_choices(conn, 1, "активный", ["другой", "третий", "четвёртый"])
    # Inactive item that uses "активный" as a distractor → Rule 1b violation
    _add_item(conn, 100, "new_word", "новый", is_active=0)
    _add_choices(conn, 100, "новый", ["активный", "другой", "третий"])

    csv_content = _csv_string([
        _make_ready_row("G001", "new_word", "новый", ["активный", "другой", "третий"], 100)
    ])
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
        f.write(csv_content)
        csv_path = f.name

    try:
        pack = build_tranche2_pack(conn, csv_path)
        assert pack["hard_blocked_count"] == 1
        assert pack["eligible_count"] == 0
        assert pack["selected_count"] == 0
    finally:
        os.unlink(csv_path)


def test_build_pack_selects_clean_items():
    conn = _make_db()
    _add_item(conn, 1, "active_word", "активный", is_active=1)
    _add_choices(conn, 1, "активный", ["другой", "третий", "четвёртый"])

    items = []
    for i in range(12):
        iid = 100 + i
        _add_item(conn, iid, f"word_{i}", f"ca_{i}", is_active=0)
        _add_choices(conn, iid, f"ca_{i}", ["d1", "d2", "d3"])
        items.append(_make_ready_row(f"G{i:03}", f"word_{i}", f"ca_{i}", ["d1", "d2", "d3"], iid, f"cg_{i}"))

    csv_content = _csv_string(items)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
        f.write(csv_content)
        csv_path = f.name

    try:
        pack = build_tranche2_pack(conn, csv_path)
        assert pack["hard_blocked_count"] == 0
        assert pack["selected_count"] == 10
        assert pack["eligible_count"] == 12
    finally:
        os.unlink(csv_path)


# ---------------------------------------------------------------------------
# write_apply_script_donotrun
# ---------------------------------------------------------------------------


def test_apply_script_contains_donotrun_header():
    pack = {
        "prepared_at": "2026-04-18T00:00:00Z",
        "selected": [
            {
                "import_item_id": 101,
                "lemma": "teste",
                "correct_answer": "тест",
                "concept_group": "misc",
                "collision_note": "CLEAN",
                "distractors": ["a", "b", "c"],
            }
        ],
    }
    with tempfile.TemporaryDirectory() as tmpdir:
        path = write_apply_script_donotrun(pack, tmpdir)
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "DO NOT RUN" in content
        assert "PREPARE ONLY" in content
        assert "ACTIVATION IS NOT AUTHORIZED" in content
        assert "101" in content
        assert "teste" in content


def test_apply_script_not_executable():
    pack = {
        "prepared_at": "2026-04-18T00:00:00Z",
        "selected": [
            {
                "import_item_id": 101,
                "lemma": "teste",
                "correct_answer": "тест",
                "concept_group": "misc",
                "collision_note": "CLEAN",
                "distractors": ["a", "b", "c"],
            }
        ],
    }
    with tempfile.TemporaryDirectory() as tmpdir:
        path = write_apply_script_donotrun(pack, tmpdir)
        mode = os.stat(path).st_mode
        assert not (mode & 0o111), "Apply script must not be executable"
