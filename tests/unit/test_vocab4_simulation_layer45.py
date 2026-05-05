from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from services.vocab4 import repo, service
from services.vocab4.attempt_state import SelectorState
from services.vocab4.exceptions import InsufficientBankError
from services.vocab4.selector import select_next

MIGRATION = Path("db/migrations_sqlite/020_vocab4_runtime.sql")

# Minimal 24-item deterministic bank that exactly fills the default quotas.
# noun=10: 1K×4, 2K×3, 5K×2, 10K×1
# verb=5:  1K×2, 2K×2, 5K×1
# adj=5:   1K×1, 2K×1, 5K×2, 10K×1
# adv=4:   1K×1, 2K×1, 5K×1, 10K×1
# Bin totals: 1K=8, 2K=7, 5K=6, 10K=3, 20K=0 — matches DEFAULT_BIN_QUOTA exactly.
_BANK_SPEC: list[tuple[str, str, int]] = [
    ("noun",      "1K",  1), ("noun",      "1K",  2),
    ("noun",      "1K",  3), ("noun",      "1K",  4),
    ("noun",      "2K",  5), ("noun",      "2K",  6), ("noun",      "2K",  7),
    ("noun",      "5K",  8), ("noun",      "5K",  9),
    ("noun",      "10K", 10),
    ("verb",      "1K",  11), ("verb",      "1K",  12),
    ("verb",      "2K",  13), ("verb",      "2K",  14),
    ("verb",      "5K",  15),
    ("adjective", "1K",  16),
    ("adjective", "2K",  17),
    ("adjective", "5K",  18), ("adjective", "5K",  19),
    ("adjective", "10K", 20),
    ("adverb",    "1K",  21),
    ("adverb",    "2K",  22),
    ("adverb",    "5K",  23),
    ("adverb",    "10K", 24),
]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _build_pool() -> list[dict]:
    """Selector-only pool (no DB). Matches the bank spec 1-to-1."""
    return [
        {"id": i, "pos": pos, "bin_name": bin_name, "freq_rank": freq_rank}
        for i, (pos, bin_name, freq_rank) in enumerate(_BANK_SPEC, start=1)
    ]


def _build_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(MIGRATION.read_text(encoding="utf-8"))
    return conn


def _seed_choices(conn: sqlite3.Connection, item_id: int) -> None:
    """Insert 6 choices for item_id; position 0 is the correct one."""
    for i in range(6):
        conn.execute(
            """
            INSERT INTO vocab4_choices (item_id, choice_text, is_correct, position_index)
            VALUES (?, ?, ?, ?)
            """,
            (item_id, f"choice_{i}", 1 if i == 0 else 0, i),
        )


def _seed_bank(conn: sqlite3.Connection) -> None:
    """Seed all 24 bank items with full choice sets into vocab4_items + vocab4_choices."""
    for pos, bin_name, freq_rank in _BANK_SPEC:
        cursor = conn.execute(
            """
            INSERT INTO vocab4_items
                (lemma, pos, bin_name, prompt, correct_choice, is_active, cert_status, freq_rank)
            VALUES (?, ?, ?, 'prompt', 'choice_0', 1, 'certified', ?)
            """,
            (f"{pos}_{bin_name}_{freq_rank}", pos, bin_name, freq_rank),
        )
        _seed_choices(conn, cursor.lastrowid)
    conn.commit()


def _run_attempt(
    conn: sqlite3.Connection,
    user_id: int,
    question_limit: int = 24,
) -> dict:
    """Run a complete attempt through service layer. Returns seen items and final DB state."""
    result = service.start_new_attempt(conn, user_id=user_id, question_limit=question_limit)
    attempt_id = result["attempt_id"]
    seen_items: list[dict] = [result["item"]]

    for _ in range(question_limit - 1):
        service.submit_answer(conn, attempt_id, seen_items[-1]["id"], None, 1)
        q = service.get_next_question(conn, attempt_id)
        seen_items.append(q["item"])

    final = service.submit_answer(conn, attempt_id, seen_items[-1]["id"], None, 1)
    attempt = repo.load_attempt(conn, attempt_id)

    return {
        "attempt_id": attempt_id,
        "seen_items": seen_items,
        "final_status": final["status"],
        "attempt": attempt,
    }


def _run_full_selection(pool: list[dict]) -> list[tuple[dict, SelectorState]]:
    """Drive select_next 24 times over the pool; returns (item, state_after) per step."""
    state = SelectorState.initial()
    steps = []
    for _ in range(24):
        item, state = select_next(pool, state)
        steps.append((item, state))
    return steps


def _expected_best_pos(state: SelectorState) -> str | None:
    """Replicate the selector's POS deficit scan to predict which POS will be chosen."""
    best_deficit = 0
    best_pos: str | None = None
    for pos in ("noun", "verb", "adjective", "adverb"):
        deficit = state.pos_quota.get(pos, 0) - state.pos_used.get(pos, 0)
        if deficit > best_deficit:
            best_deficit = deficit
            best_pos = pos
    return best_pos


# ---------------------------------------------------------------------------
# selector-layer invariant tests (no DB — isolates selector algorithm)
# ---------------------------------------------------------------------------

def test_no_item_selected_twice() -> None:
    pool = _build_pool()
    steps = _run_full_selection(pool)
    selected_ids = [item["id"] for item, _ in steps]
    assert len(selected_ids) == len(set(selected_ids))


def test_pos_quota_never_exceeded() -> None:
    pool = _build_pool()
    state = SelectorState.initial()
    for step in range(24):
        item, state = select_next(pool, state)
        for pos, quota in state.pos_quota.items():
            assert state.pos_used.get(pos, 0) <= quota, (
                f"step {step}: pos_used[{pos}]={state.pos_used.get(pos, 0)} > quota={quota}"
            )


def test_selected_pos_always_has_highest_deficit() -> None:
    pool = _build_pool()
    state = SelectorState.initial()
    for step in range(24):
        expected_pos = _expected_best_pos(state)
        item, state = select_next(pool, state)
        assert item["pos"] == expected_pos, (
            f"step {step}: expected pos={expected_pos!r}, got {item['pos']!r}"
        )


def test_bin_positive_deficit_beats_least_used() -> None:
    pool = _build_pool()
    state = SelectorState.initial()
    for step in range(24):
        available_bins = {
            p["bin_name"]
            for p in pool
            if p["pos"] == _expected_best_pos(state)
            and p["id"] not in state.shown_item_ids
        }
        positive_deficit_bins = {
            b for b in available_bins
            if (state.bin_quota.get(b, 0) - state.bin_used.get(b, 0)) > 0
        }
        item, state = select_next(pool, state)
        if positive_deficit_bins:
            assert item["bin_name"] in positive_deficit_bins, (
                f"step {step}: selected {item['bin_name']!r} but positive-deficit "
                f"bins exist: {positive_deficit_bins}"
            )


def test_20k_never_selected() -> None:
    pool = _build_pool()
    steps = _run_full_selection(pool)
    for step, (item, _) in enumerate(steps):
        assert item["bin_name"] != "20K", f"step {step}: 20K item selected (quota=0)"


def test_all_24_items_exhausted_after_full_run() -> None:
    pool = _build_pool()
    steps = _run_full_selection(pool)
    assert {item["id"] for item, _ in steps} == {item["id"] for item in pool}


def test_25th_selection_raises_insufficient_bank() -> None:
    pool = _build_pool()
    state = SelectorState.initial()
    for _ in range(24):
        _, state = select_next(pool, state)
    with pytest.raises(InsufficientBankError):
        select_next(pool, state)


# ---------------------------------------------------------------------------
# regression tests — pin the deterministic selection sequence
# ---------------------------------------------------------------------------

def test_first_selection_is_noun_1k_freq1() -> None:
    pool = _build_pool()
    state = SelectorState.initial()
    item, _ = select_next(pool, state)
    assert item["pos"] == "noun"
    assert item["bin_name"] == "1K"
    assert item["freq_rank"] == 1


def test_final_pos_used_equals_quota() -> None:
    pool = _build_pool()
    steps = _run_full_selection(pool)
    _, final_state = steps[-1]
    assert final_state.pos_used == final_state.pos_quota


def test_pos_sequence_first_eight() -> None:
    # Deficit drainage: noun leads at 10, drains to 4 before verb/adjective (both 5)
    # overtake it; verb beats adjective at step 6 by KNOWN_POS iteration order;
    # adjective overtakes at step 7 when verb drops to 4.
    expected = ["noun", "noun", "noun", "noun", "noun", "noun", "verb", "adjective"]
    pool = _build_pool()
    state = SelectorState.initial()
    for step, exp_pos in enumerate(expected):
        item, state = select_next(pool, state)
        assert item["pos"] == exp_pos, (
            f"step {step}: expected {exp_pos!r}, got {item['pos']!r}"
        )


# ---------------------------------------------------------------------------
# full-stack simulation tests — migration → repo → service → selector → repo
# ---------------------------------------------------------------------------

def test_24_question_attempt_has_no_duplicates() -> None:
    conn = _build_conn()
    _seed_bank(conn)
    result = _run_attempt(conn, user_id=1)
    seen_ids = [item["id"] for item in result["seen_items"]]
    assert result["final_status"] == "finished"
    assert len(seen_ids) == 24
    assert len(set(seen_ids)) == 24
    assert result["attempt"]["status"] == "finished"
    assert result["attempt"]["current_step"] == 24


def test_24_question_attempt_hits_pos_quota_exactly_with_sufficient_bank() -> None:
    conn = _build_conn()
    _seed_bank(conn)
    result = _run_attempt(conn, user_id=1)
    state = SelectorState.from_json(result["attempt"]["selector_state_json"])
    assert state.pos_used == state.pos_quota


def test_24_question_attempt_respects_bin_quota_when_bank_sufficient() -> None:
    conn = _build_conn()
    _seed_bank(conn)
    result = _run_attempt(conn, user_id=1)
    state = SelectorState.from_json(result["attempt"]["selector_state_json"])
    for bin_name, quota in state.bin_quota.items():
        assert state.bin_used.get(bin_name, 0) == quota, (
            f"bin={bin_name!r}: used={state.bin_used.get(bin_name, 0)} != quota={quota}"
        )


def test_multiple_attempts_are_deterministic() -> None:
    conn = _build_conn()
    _seed_bank(conn)
    r1 = _run_attempt(conn, user_id=1)
    r2 = _run_attempt(conn, user_id=2)
    ids1 = [item["id"] for item in r1["seen_items"]]
    ids2 = [item["id"] for item in r2["seen_items"]]
    assert ids1 == ids2


def test_insufficient_bank_fails_closed() -> None:
    conn = _build_conn()
    # seed exactly 1 item — enough to start but not to continue
    cursor = conn.execute(
        """
        INSERT INTO vocab4_items
            (lemma, pos, bin_name, prompt, correct_choice, is_active, cert_status, freq_rank)
        VALUES ('solo', 'noun', '1K', 'prompt', 'choice_0', 1, 'certified', 1)
        """
    )
    _seed_choices(conn, cursor.lastrowid)
    conn.commit()

    result = service.start_new_attempt(conn, user_id=1)
    attempt_id = result["attempt_id"]

    with pytest.raises(InsufficientBankError):
        service.get_next_question(conn, attempt_id)

    # attempt must remain in_progress — no state corruption
    attempt = repo.load_attempt(conn, attempt_id)
    assert attempt["status"] == "in_progress"


def test_state_json_matches_answered_items_after_attempt() -> None:
    conn = _build_conn()
    _seed_bank(conn)
    result = _run_attempt(conn, user_id=1)
    attempt_id = result["attempt_id"]

    state = SelectorState.from_json(result["attempt"]["selector_state_json"])

    rows = conn.execute(
        "SELECT item_id FROM vocab4_answers WHERE attempt_id = ?",
        (attempt_id,),
    ).fetchall()
    answered_ids = sorted(row[0] for row in rows)

    assert sorted(state.shown_item_ids) == answered_ids


def test_no_inactive_or_uncertified_items_selected() -> None:
    conn = _build_conn()
    _seed_bank(conn)

    # decoys: same POS/bin slots, excluded by is_active or cert_status
    decoy_specs = [
        ("decoy_inactive",  "noun", "1K", 0, "certified"),
        ("decoy_draft",     "noun", "1K", 1, "draft"),
        ("decoy_rejected",  "noun", "1K", 1, "rejected"),
    ]
    for lemma, pos, bin_name, is_active, cert_status in decoy_specs:
        cursor = conn.execute(
            """
            INSERT INTO vocab4_items
                (lemma, pos, bin_name, prompt, correct_choice, is_active, cert_status)
            VALUES (?, ?, ?, 'prompt', 'choice_0', ?, ?)
            """,
            (lemma, pos, bin_name, is_active, cert_status),
        )
        _seed_choices(conn, cursor.lastrowid)
    conn.commit()

    decoy_lemmas = {spec[0] for spec in decoy_specs}
    result = _run_attempt(conn, user_id=1)
    seen_lemmas = {item["lemma"] for item in result["seen_items"]}

    assert seen_lemmas.isdisjoint(decoy_lemmas)


def test_100_attempts_smoke_no_randomness_no_crash() -> None:
    conn = _build_conn()
    _seed_bank(conn)

    reference_ids: list[int] | None = None
    for user_id in range(1, 101):
        result = _run_attempt(conn, user_id=user_id)
        assert result["final_status"] == "finished", f"user {user_id}: did not finish"
        seen_ids = [item["id"] for item in result["seen_items"]]
        assert len(set(seen_ids)) == 24, f"user {user_id}: duplicate items"
        if reference_ids is None:
            reference_ids = seen_ids
        else:
            assert seen_ids == reference_ids, f"user {user_id}: non-deterministic sequence"
