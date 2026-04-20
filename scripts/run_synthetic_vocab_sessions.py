#!/usr/bin/env python3
"""
run_synthetic_vocab_sessions.py

Synthetic vocab session harness for smoke, coverage, and selector sanity checks.

SYNTHETIC SESSIONS — MONITORING EXCLUSION GUARANTEE
  Every session produced by this harness is explicitly marked:
    - mode_runs.source = 'synthetic_harness'       (creation-time)
    - completion_reason = 'simulation_exhausted'    (completion-time)
  The live monitoring filter requires completion_reason='question_limit_reached',
  which excludes all harness sessions by design. They will never contribute to
  tranche-gate decisions.

DIRECT INSERT NOTE
  vocab_answers rows are inserted directly by this harness. The sync code path
  (services/vocab_runtime/repo.py:log_event) does not write vocab_answers.
  The monitoring runner reads vocab_answers for signals S1-S4; these direct
  inserts ensure harness sessions produce realistic signal data if ever
  compared against live sessions in isolation tests.

PROFILES
  strong        — 90% correct answers
  medium        — 55% correct answers
  weak          — 20% correct answers
  dont_know_heavy — 40% dont_know, 50% correct of remainder

USAGE
  python3 scripts/run_synthetic_vocab_sessions.py
  python3 scripts/run_synthetic_vocab_sessions.py --profile strong --n-sessions 3
  python3 scripts/run_synthetic_vocab_sessions.py --profile all --n-sessions 2
  python3 scripts/run_synthetic_vocab_sessions.py --db data/lingua_staging.db
  python3 scripts/run_synthetic_vocab_sessions.py --dry-run

Read-only mode (--dry-run): prints plan without writing to DB.
"""
from __future__ import annotations

import argparse
import os
import random
import sqlite3
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from scripts.noun10k_monitoring_runner import (
    SYNTHETIC_SESSION_SOURCE,
    SYNTHETIC_SESSION_COMPLETION_REASON,
)
from services.vocab_runtime.repo import (
    finish_attempt,
    get_active_attempt,
    log_event,
    start_attempt,
)
from services.vocab_runtime.selector import get_next_item

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_DB = "data/lingua_staging.db"
DEFAULT_N_SESSIONS = 1
DEFAULT_QUESTION_LIMIT = 24

# Synthetic users — telegram_user_id range 9_000_001–9_999_999, is_bot=1
_SYNTHETIC_USER_BASE_TG_ID = 9_000_001

_PROFILE_NAMES = ("strong", "medium", "weak", "dont_know_heavy")

# Profile definitions: (correct_rate, dont_know_rate)
# correct_rate applies to non-dont_know answers only
_PROFILES: dict[str, dict[str, float]] = {
    "strong":          {"correct_rate": 0.90, "dont_know_rate": 0.02},
    "medium":          {"correct_rate": 0.55, "dont_know_rate": 0.10},
    "weak":            {"correct_rate": 0.20, "dont_know_rate": 0.05},
    "dont_know_heavy": {"correct_rate": 0.55, "dont_know_rate": 0.40},
}


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------

def _upsert_synthetic_user(conn: sqlite3.Connection, *, profile: str) -> int:
    """Return internal user_id for the synthetic user for this profile."""
    profile_index = _PROFILE_NAMES.index(profile)
    tg_id = _SYNTHETIC_USER_BASE_TG_ID + profile_index
    username = f"synthetic_{profile}"

    conn.execute(
        """
        INSERT INTO users (telegram_user_id, username, first_name, is_bot)
        VALUES (?, ?, ?, 1)
        ON CONFLICT(telegram_user_id) DO UPDATE SET username=excluded.username
        """,
        (tg_id, username, f"Synthetic ({profile})"),
    )
    conn.commit()
    row = conn.execute(
        "SELECT id FROM users WHERE telegram_user_id = ?", (tg_id,)
    ).fetchone()
    return int(row["id"])


# ---------------------------------------------------------------------------
# Answer simulation
# ---------------------------------------------------------------------------

def _simulate_answer(
    conn: sqlite3.Connection,
    *,
    item_id: int,
    profile_cfg: dict[str, float],
    rng: random.Random,
) -> tuple[str, int]:
    """Return (event_type, is_correct): ('answer'|'dont_know', 0|1)."""
    if rng.random() < profile_cfg["dont_know_rate"]:
        return "dont_know", 0

    is_correct = 1 if rng.random() < profile_cfg["correct_rate"] else 0
    return "answer", is_correct


def _get_correct_choice_id(
    conn: sqlite3.Connection, *, item_id: int
) -> int | None:
    row = conn.execute(
        "SELECT id FROM vocab_choices WHERE item_id = ? AND is_correct = 1 LIMIT 1",
        (item_id,),
    ).fetchone()
    return int(row["id"]) if row else None


def _get_wrong_choice_id(
    conn: sqlite3.Connection, *, item_id: int, rng: random.Random
) -> int | None:
    rows = conn.execute(
        "SELECT id FROM vocab_choices WHERE item_id = ? AND is_correct = 0",
        (item_id,),
    ).fetchall()
    if not rows:
        return None
    return int(rng.choice(rows)["id"])


# ---------------------------------------------------------------------------
# Core session runner
# ---------------------------------------------------------------------------

def run_session(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    profile: str,
    question_limit: int = DEFAULT_QUESTION_LIMIT,
    rng: random.Random,
    dry_run: bool = False,
    verbose: bool = True,
) -> dict:
    """Run one synthetic vocab session. Returns summary dict."""
    profile_cfg = _PROFILES[profile]

    if dry_run:
        return {
            "dry_run": True,
            "profile": profile,
            "user_id": user_id,
            "questions": 0,
            "correct": 0,
            "dont_know": 0,
            "attempt_id": None,
            "mode_run_id": None,
        }

    # 1. Create mode_run with explicit synthetic source marker
    cur = conn.execute(
        "INSERT INTO mode_runs (mode, user_id, status, source) VALUES (?, ?, ?, ?)",
        ("vocab", user_id, "started", SYNTHETIC_SESSION_SOURCE),
    )
    mode_run_id = int(cur.lastrowid)
    conn.commit()

    # 2. Create vocab_attempt
    attempt_id = start_attempt(conn, user_id=user_id, mode_run_id=mode_run_id)

    questions_answered = 0
    correct_count = 0
    dont_know_count = 0

    # 3. Question loop using real selector
    for _ in range(question_limit):
        item = get_next_item(conn, attempt_id=attempt_id)
        if item is None:
            break  # pool exhausted

        item_id = int(item["id"])

        # 3a. Log shown event (drives selector anti-repeat)
        log_event(conn, attempt_id=attempt_id, user_id=user_id, item_id=item_id, event_type="shown")

        # 3b. Simulate answer based on profile
        event_type, is_correct = _simulate_answer(
            conn, item_id=item_id, profile_cfg=profile_cfg, rng=rng
        )

        # 3c. Log answer event (bumps attempt counters)
        log_event(
            conn,
            attempt_id=attempt_id,
            user_id=user_id,
            item_id=item_id,
            event_type=event_type,
            is_correct=is_correct,
        )

        # 3d. Write vocab_answers directly (monitoring reads this table).
        #     log_event does NOT write vocab_answers in the sync path.
        if event_type == "dont_know":
            answer_status = "dont_know"
            choice_id = None
        elif is_correct:
            answer_status = "correct"
            choice_id = _get_correct_choice_id(conn, item_id=item_id)
        else:
            answer_status = "wrong"
            choice_id = _get_wrong_choice_id(conn, item_id=item_id, rng=rng)

        conn.execute(
            """
            INSERT OR IGNORE INTO vocab_answers
                (attempt_id, item_id, selected_choice_id, answer_status, answer_kind, is_correct)
            VALUES (?, ?, ?, ?, 'selected', ?)
            """,
            (attempt_id, item_id, choice_id, answer_status, is_correct),
        )
        conn.commit()

        questions_answered += 1
        if is_correct:
            correct_count += 1
        if event_type == "dont_know":
            dont_know_count += 1

        if verbose:
            lemma = item["lemma"]
            tag = "✓" if is_correct else ("?" if event_type == "dont_know" else "✗")
            print(f"    Q{questions_answered:02d} [{tag}] {lemma}")

    # 4. Finish with explicit synthetic completion reason
    finish_attempt(
        conn,
        attempt_id=attempt_id,
        completion_reason=SYNTHETIC_SESSION_COMPLETION_REASON,
    )

    return {
        "dry_run": False,
        "profile": profile,
        "user_id": user_id,
        "attempt_id": attempt_id,
        "mode_run_id": mode_run_id,
        "questions_answered": questions_answered,
        "correct_count": correct_count,
        "dont_know_count": dont_know_count,
        "completion_reason": SYNTHETIC_SESSION_COMPLETION_REASON,
        "source": SYNTHETIC_SESSION_SOURCE,
    }


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def run_profile(
    conn: sqlite3.Connection,
    *,
    profile: str,
    n_sessions: int,
    question_limit: int = DEFAULT_QUESTION_LIMIT,
    seed: int | None = None,
    dry_run: bool = False,
    verbose: bool = True,
) -> list[dict]:
    rng = random.Random(seed)

    if dry_run:
        user_id = f"<synthetic_{profile}>"  # type: ignore[assignment]
    else:
        user_id = _upsert_synthetic_user(conn, profile=profile)

    results = []
    for i in range(n_sessions):
        if verbose:
            print(f"\n  [Session {i + 1}/{n_sessions}] profile={profile} user_id={user_id}")
        result = run_session(
            conn,
            user_id=user_id,
            profile=profile,
            question_limit=question_limit,
            rng=rng,
            dry_run=dry_run,
            verbose=verbose,
        )
        results.append(result)
        if not dry_run:
            print(
                f"  → attempt_id={result['attempt_id']} "
                f"mode_run_id={result['mode_run_id']} "
                f"q={result['questions_answered']} "
                f"correct={result['correct_count']} "
                f"dk={result['dont_know_count']}"
            )
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Synthetic vocab session harness. Read-only if --dry-run."
    )
    parser.add_argument("--db", default=DEFAULT_DB)
    parser.add_argument(
        "--profile",
        choices=[*_PROFILE_NAMES, "all"],
        default="medium",
        help="Profile to run (default: medium)",
    )
    parser.add_argument("--n-sessions", type=int, default=DEFAULT_N_SESSIONS)
    parser.add_argument("--question-limit", type=int, default=DEFAULT_QUESTION_LIMIT)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    if not os.path.exists(args.db):
        print(f"ERROR: DB not found: {args.db}", file=sys.stderr)
        return 1

    verbose = not args.quiet

    if args.dry_run:
        print("[DRY-RUN] No DB writes will be performed.")

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row

    profiles_to_run = _PROFILE_NAMES if args.profile == "all" else (args.profile,)

    all_results: list[dict] = []
    try:
        for profile in profiles_to_run:
            print(f"\n{'=' * 60}")
            print(f"PROFILE: {profile}  sessions={args.n_sessions}  q_limit={args.question_limit}")
            print(f"{'=' * 60}")
            results = run_profile(
                conn,
                profile=profile,
                n_sessions=args.n_sessions,
                question_limit=args.question_limit,
                seed=args.seed,
                dry_run=args.dry_run,
                verbose=verbose,
            )
            all_results.extend(results)
    finally:
        conn.close()

    print(f"\n{'=' * 60}")
    print(f"HARNESS SUMMARY  dry_run={args.dry_run}")
    print(f"{'=' * 60}")
    for r in all_results:
        if r["dry_run"]:
            print(f"  [DRY-RUN] profile={r['profile']}")
        else:
            pct = round(100 * r["correct_count"] / r["questions_answered"], 1) if r["questions_answered"] else 0
            print(
                f"  attempt_id={r['attempt_id']} profile={r['profile']} "
                f"q={r['questions_answered']} correct={r['correct_count']} ({pct}%) "
                f"dk={r['dont_know_count']} "
                f"source={r['source']} reason={r['completion_reason']}"
            )

    print(f"\nSYNTHETIC MARKER: source='{SYNTHETIC_SESSION_SOURCE}'"
          f"  completion_reason='{SYNTHETIC_SESSION_COMPLETION_REASON}'")
    print("MONITORING EXCLUSION: guaranteed — live filter requires "
          "completion_reason='question_limit_reached'")

    return 0


if __name__ == "__main__":
    sys.exit(main())
