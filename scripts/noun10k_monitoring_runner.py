#!/usr/bin/env python3
"""
noun10k_monitoring_runner.py

Read-only monitoring runner for noun/10K and verb/10K post-activation diagnostics.
Computes the 4 canonical signals from the monitoring plan and evaluates T1-T4
activation triggers for each POS/bin track separately.

REAL SESSION FILTER (PROVISIONAL)
  status='finished' AND completion_reason='question_limit_reached'
  Rationale: 'question_limit_reached' is set exclusively by
  modes/vocab/router.py:332 (live Telegram bot runtime). No is_synthetic
  marker exists in the schema. This filter is provisional.
  Source: inspect_real_session_criterion.py audit, 2026-04-18.

SAFETY
  This script is strictly read-only. It makes zero writes to the database.
  Synthetic sessions (completion_reason='simulation_exhausted') are excluded.

USAGE
  python3 scripts/noun10k_monitoring_runner.py
  python3 scripts/noun10k_monitoring_runner.py --db data/lingua_staging.db
  python3 scripts/noun10k_monitoring_runner.py --db data/lingua_staging.db \\
      --output-dir diagnostics_exports/

OUTPUT
  Prints a human-readable summary to stdout.
  Writes a JSON report to --output-dir (default: diagnostics_exports/).
  Report filename: noun10k_monitoring_report_<YYYYMMDDTHHMMSSZ>.json

  Report structure:
    {
      "noun_10k": { ... noun/10K signals and triggers ... },
      "verb_10k": { ... verb/10K signals and triggers ... },
      ... flat top-level keys (noun/10K, backward compat) ...
    }
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sqlite3
import statistics
import sys

# ---------------------------------------------------------------------------
# Constants — noun/10K thresholds from noun10k_post_activation_monitoring_plan.md
# ---------------------------------------------------------------------------

REAL_SESSION_FILTER = (
    "status = 'finished' AND completion_reason = 'question_limit_reached'"
)
REAL_SESSION_FILTER_NOTE = (
    "PROVISIONAL: 'question_limit_reached' set only by modes/vocab/router.py:332"
)

MINIMUM_SESSIONS = 30
MINIMUM_USERS = 3
MINIMUM_ANSWERS_PER_ITEM = 5

T1_REPEAT_RATE_CONCERN = 0.33
T2_MEAN_ITEMS_DEPLETION = 1.5
T2_CONSECUTIVE_WINDOW = 10
T3_MIN_ITEMS_WITH_3_SHOWN = 10
T3_MIN_SHOWN = 3
T4_SKEW_TOP_THRESHOLD = 8
T4_SKEW_MEDIAN_THRESHOLD = 3

NOUN_10K_POS = "noun"
NOUN_10K_BIN = "10K"

# ---------------------------------------------------------------------------
# Constants — verb/10K thresholds from pos_next_track_execution_plan.md Stage E
# ---------------------------------------------------------------------------

VERB_10K_POS = "verb"
VERB_10K_BIN = "10K"

# T2: verbs have higher selector target (7/session vs nouns) → pool depletes faster
VERB_T2_MEAN_ITEMS_DEPLETION = 2.0
# T3: 9 verb items active → threshold is 8 (vs 10 for 13 nouns)
VERB_T3_MIN_ITEMS_WITH_3_SHOWN = 8


# ---------------------------------------------------------------------------
# Data fetch functions (all read-only, parameterized by pos/bin_name)
# ---------------------------------------------------------------------------


def fetch_real_session_ids(conn: sqlite3.Connection) -> list[int]:
    rows = conn.execute(
        "SELECT id FROM vocab_attempts WHERE "
        + REAL_SESSION_FILTER
        + " ORDER BY id"
    ).fetchall()
    return [r[0] for r in rows]


def fetch_real_session_user_count(conn: sqlite3.Connection, session_ids: list[int]) -> int:
    if not session_ids:
        return 0
    placeholders = ",".join("?" * len(session_ids))
    row = conn.execute(
        f"SELECT COUNT(DISTINCT user_id) AS cnt FROM vocab_attempts "
        f"WHERE id IN ({placeholders})",
        session_ids,
    ).fetchone()
    return int(row[0])


def fetch_signal1_items_per_session(
    conn: sqlite3.Connection,
    session_ids: list[int],
    pos: str = NOUN_10K_POS,
    bin_name: str = NOUN_10K_BIN,
) -> list[dict]:
    """Signal 1: items shown per complete real session for the given pos/bin."""
    if not session_ids:
        return []
    placeholders = ",".join("?" * len(session_ids))
    rows = conn.execute(
        f"""
        SELECT att.id AS attempt_id,
               COUNT(DISTINCT va.item_id) AS items_shown
        FROM vocab_attempts att
        JOIN vocab_answers va ON va.attempt_id = att.id
        JOIN vocab_items vi ON vi.id = va.item_id
        WHERE vi.pos = ?
          AND vi.bin_name = ?
          AND vi.is_active = 1
          AND att.id IN ({placeholders})
        GROUP BY att.id
        ORDER BY att.id
        """,
        [pos, bin_name] + session_ids,
    ).fetchall()
    return [{"attempt_id": r[0], "items_shown": r[1]} for r in rows]


def fetch_signal2_exposure_per_item(
    conn: sqlite3.Connection,
    session_ids: list[int],
    pos: str = NOUN_10K_POS,
    bin_name: str = NOUN_10K_BIN,
) -> list[dict]:
    """Signal 2: per-item exposure counts from real sessions only.

    Deliberately avoids vocab_item_exposure (which includes synthetic runs).
    """
    placeholders = ",".join("?" * len(session_ids)) if session_ids else ""

    if session_ids:
        rows = conn.execute(
            f"""
            SELECT vi.id,
                   vi.lemma,
                   COUNT(DISTINCT va.attempt_id) AS sessions_shown,
                   COUNT(va.id) AS total_answers
            FROM vocab_items vi
            LEFT JOIN vocab_answers va
                   ON va.item_id = vi.id
                  AND va.attempt_id IN ({placeholders})
            WHERE vi.pos = ?
              AND vi.bin_name = ?
              AND vi.is_active = 1
            GROUP BY vi.id, vi.lemma
            ORDER BY sessions_shown DESC
            """,
            session_ids + [pos, bin_name],
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT vi.id, vi.lemma, 0 AS sessions_shown, 0 AS total_answers
            FROM vocab_items vi
            WHERE vi.pos = ? AND vi.bin_name = ? AND vi.is_active = 1
            ORDER BY vi.id
            """,
            [pos, bin_name],
        ).fetchall()

    return [
        {
            "item_id": r[0],
            "lemma": r[1],
            "sessions_shown": r[2],
            "total_answers": r[3],
        }
        for r in rows
    ]


def fetch_signal3_repeat_rate(
    conn: sqlite3.Connection,
    session_ids: list[int],
    pos: str = NOUN_10K_POS,
    bin_name: str = NOUN_10K_BIN,
) -> dict:
    """Signal 3: per-user repeat rate across consecutive sessions.

    For each user, iterates consecutive session pairs (N-1, N) and computes
    what fraction of pos/bin items in session N were also in session N-1.
    """
    if not session_ids:
        return {"pairs_evaluated": 0, "mean_repeat_rate": None, "max_repeat_rate": None}

    placeholders = ",".join("?" * len(session_ids))

    rows = conn.execute(
        f"""
        SELECT att.user_id,
               att.id AS attempt_id,
               va.item_id
        FROM vocab_attempts att
        JOIN vocab_answers va ON va.attempt_id = att.id
        JOIN vocab_items vi ON vi.id = va.item_id
        WHERE vi.pos = ?
          AND vi.bin_name = ?
          AND vi.is_active = 1
          AND att.id IN ({placeholders})
        ORDER BY att.user_id, att.id
        """,
        [pos, bin_name] + session_ids,
    ).fetchall()

    user_sessions: dict[int, dict[int, set]] = {}
    for user_id, attempt_id, item_id in rows:
        if user_id not in user_sessions:
            user_sessions[user_id] = {}
        if attempt_id not in user_sessions[user_id]:
            user_sessions[user_id][attempt_id] = set()
        user_sessions[user_id][attempt_id].add(item_id)

    per_pair_rates: list[float] = []
    pair_details: list[dict] = []

    for user_id, sessions_map in user_sessions.items():
        sorted_attempts = sorted(sessions_map.keys())
        for i in range(1, len(sorted_attempts)):
            prev_id = sorted_attempts[i - 1]
            curr_id = sorted_attempts[i]
            prev_items = sessions_map[prev_id]
            curr_items = sessions_map[curr_id]
            if not curr_items:
                continue
            overlap = len(prev_items & curr_items)
            rate = overlap / len(curr_items)
            per_pair_rates.append(rate)
            pair_details.append(
                {
                    "user_id": user_id,
                    "session_n_minus_1": prev_id,
                    "session_n": curr_id,
                    "items_n_minus_1": len(prev_items),
                    "items_n": len(curr_items),
                    "overlap": overlap,
                    "repeat_rate": round(rate, 4),
                }
            )

    if not per_pair_rates:
        return {"pairs_evaluated": 0, "mean_repeat_rate": None, "max_repeat_rate": None, "pairs": []}

    return {
        "pairs_evaluated": len(per_pair_rates),
        "mean_repeat_rate": round(statistics.mean(per_pair_rates), 4),
        "max_repeat_rate": round(max(per_pair_rates), 4),
        "pairs": pair_details,
    }


def fetch_signal4_correctness(
    conn: sqlite3.Connection,
    session_ids: list[int],
    pos: str = NOUN_10K_POS,
    bin_name: str = NOUN_10K_BIN,
) -> list[dict]:
    """Signal 4: per-item correctness rate from real sessions, min 5 answers."""
    if not session_ids:
        return []
    placeholders = ",".join("?" * len(session_ids))
    rows = conn.execute(
        f"""
        SELECT vi.id,
               vi.lemma,
               vi.cefr_estimate,
               COUNT(*) AS total_answers,
               SUM(CASE WHEN va.is_correct = 1 THEN 1 ELSE 0 END) AS correct_count,
               ROUND(
                 100.0 * SUM(CASE WHEN va.is_correct = 1 THEN 1 ELSE 0 END) / COUNT(*),
                 1
               ) AS pct_correct
        FROM vocab_answers va
        JOIN vocab_items vi ON vi.id = va.item_id
        WHERE vi.pos = ?
          AND vi.bin_name = ?
          AND vi.is_active = 1
          AND va.attempt_id IN ({placeholders})
        GROUP BY vi.id, vi.lemma, vi.cefr_estimate
        HAVING COUNT(*) >= ?
        ORDER BY pct_correct DESC
        """,
        [pos, bin_name] + session_ids + [MINIMUM_ANSWERS_PER_ITEM],
    ).fetchall()
    return [
        {
            "item_id": r[0],
            "lemma": r[1],
            "cefr_estimate": r[2],
            "total_answers": r[3],
            "correct_count": r[4],
            "pct_correct": r[5],
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Trigger evaluation (parameterized thresholds for noun vs verb)
# ---------------------------------------------------------------------------


def evaluate_triggers(
    session_ids: list[int],
    distinct_users: int,
    signal1: list[dict],
    signal2: list[dict],
    signal3: dict,
    signal4: list[dict],
    t2_depletion: float = T2_MEAN_ITEMS_DEPLETION,
    t3_min_items: int = T3_MIN_ITEMS_WITH_3_SHOWN,
) -> dict:
    """Evaluate T1-T4. Returns trigger results and a final verdict.

    t2_depletion: threshold for T2 (noun=1.5, verb=2.0)
    t3_min_items: minimum items needing sessions_shown>=3 for T3 (noun=10, verb=8)
    """
    total_sessions = len(session_ids)
    minimum_met = total_sessions >= MINIMUM_SESSIONS and distinct_users >= MINIMUM_USERS

    if not minimum_met:
        return {
            "minimum_sample_met": False,
            "total_sessions": total_sessions,
            "distinct_users": distinct_users,
            "minimum_sessions_required": MINIMUM_SESSIONS,
            "minimum_users_required": MINIMUM_USERS,
            "T1": None,
            "T2": None,
            "T3": None,
            "T4": None,
            "verdict": "INSUFFICIENT_DATA",
            "verdict_note": (
                f"Need {MINIMUM_SESSIONS} complete sessions and {MINIMUM_USERS} users. "
                f"Currently {total_sessions} sessions, {distinct_users} users."
            ),
        }

    # T1: repeat rate
    mean_repeat = signal3.get("mean_repeat_rate")
    t1_fires = mean_repeat is not None and mean_repeat > T1_REPEAT_RATE_CONCERN
    t1 = {
        "code": "REPEAT_SATURATION",
        "fires": t1_fires,
        "mean_repeat_rate": mean_repeat,
        "threshold": T1_REPEAT_RATE_CONCERN,
    }

    # T2: mean items per session < threshold over last 10 consecutive sessions
    if len(signal1) >= T2_CONSECUTIVE_WINDOW:
        last_n = signal1[-T2_CONSECUTIVE_WINDOW:]
        mean_items = statistics.mean(r["items_shown"] for r in last_n)
    elif signal1:
        last_n = signal1
        mean_items = statistics.mean(r["items_shown"] for r in signal1)
    else:
        mean_items = 0.0
        last_n = []
    t2_fires = mean_items < t2_depletion
    t2 = {
        "code": "POOL_DEPLETION",
        "fires": t2_fires,
        "mean_items_per_session": round(mean_items, 4),
        "sessions_evaluated": len(last_n),
        "threshold": t2_depletion,
    }

    # T3: fewer than t3_min_items items have sessions_shown >= 3
    items_with_sufficient_exposure = sum(
        1 for r in signal2 if r["sessions_shown"] >= T3_MIN_SHOWN
    )
    t3_fires = items_with_sufficient_exposure < t3_min_items
    t3 = {
        "code": "COVERAGE_FAILURE",
        "fires": t3_fires,
        "items_with_shown_gte_3": items_with_sufficient_exposure,
        "total_active_items": len(signal2),
        "threshold": t3_min_items,
    }

    # T4: any item sessions_shown >= 8 while pool median < 3
    shown_counts = [r["sessions_shown"] for r in signal2]
    pool_median = statistics.median(shown_counts) if shown_counts else 0
    top_shown = max(shown_counts) if shown_counts else 0
    t4_fires = top_shown >= T4_SKEW_TOP_THRESHOLD and pool_median < T4_SKEW_MEDIAN_THRESHOLD
    t4 = {
        "code": "EXPOSURE_SKEW",
        "fires": t4_fires,
        "max_sessions_shown": top_shown,
        "pool_median_sessions_shown": pool_median,
        "top_threshold": T4_SKEW_TOP_THRESHOLD,
        "median_threshold": T4_SKEW_MEDIAN_THRESHOLD,
    }

    # Item correctness flags
    broken_items = [r for r in signal4 if r["pct_correct"] < 20.0]
    too_easy_items = [r for r in signal4 if r["pct_correct"] > 85.0]

    any_trigger = t1_fires or t2_fires or t3_fires or t4_fires
    has_broken_items = bool(broken_items)

    if has_broken_items:
        verdict = "INVESTIGATE_SIGNAL"
        verdict_note = (
            f"Broken items detected (pct_correct < 20): "
            f"{[r['lemma'] for r in broken_items]}. Fix before activation."
        )
    elif any_trigger:
        verdict = "PREPARE_NEXT_TRANCHE"
        fired = [t["code"] for t in [t1, t2, t3, t4] if t["fires"]]
        verdict_note = f"Trigger(s) fired: {fired}. Review tranche 2 activation pack."
    else:
        verdict = "HOLD"
        verdict_note = "No triggers fired. Continue monitoring."

    return {
        "minimum_sample_met": True,
        "total_sessions": total_sessions,
        "distinct_users": distinct_users,
        "T1": t1,
        "T2": t2,
        "T3": t3,
        "T4": t4,
        "broken_items": broken_items,
        "too_easy_items": too_easy_items,
        "verdict": verdict,
        "verdict_note": verdict_note,
    }


# ---------------------------------------------------------------------------
# Section builder (shared by noun/10K and verb/10K)
# ---------------------------------------------------------------------------


def _build_section(
    conn: sqlite3.Connection,
    session_ids: list[int],
    distinct_users: int,
    pos: str,
    bin_name: str,
    t2_depletion: float,
    t3_min_items: int,
) -> dict:
    """Build one monitoring section (all 4 signals + trigger eval) for a pos/bin."""
    label = f"{pos}/{bin_name}"
    signal1 = fetch_signal1_items_per_session(conn, session_ids, pos, bin_name)
    signal2 = fetch_signal2_exposure_per_item(conn, session_ids, pos, bin_name)
    signal3 = fetch_signal3_repeat_rate(conn, session_ids, pos, bin_name)
    signal4 = fetch_signal4_correctness(conn, session_ids, pos, bin_name)
    triggers = evaluate_triggers(
        session_ids, distinct_users, signal1, signal2, signal3, signal4,
        t2_depletion=t2_depletion,
        t3_min_items=t3_min_items,
    )

    mean_items = (
        round(statistics.mean(r["items_shown"] for r in signal1), 4)
        if signal1
        else None
    )

    return {
        "pos": pos,
        "bin_name": bin_name,
        "summary": {
            "total_real_sessions": len(session_ids),
            "distinct_real_users": distinct_users,
            "sessions_with_items": len(signal1),
            "mean_items_per_session": mean_items,
            "active_items": len(signal2),
        },
        "signal_scope_note": (
            f"Signal 1 and Signal 3 count only items currently active in the {label} pool "
            f"(vi.is_active=1). Legacy {label} items deactivated before the monitoring "
            f"window are excluded. Signal 2 and Signal 4 were already filtering is_active=1."
        ),
        "signal1_items_per_session": signal1,
        "signal2_exposure_per_item": signal2,
        "signal3_repeat_rate": signal3,
        "signal4_correctness": signal4,
        "trigger_evaluation": triggers,
        "verdict": triggers["verdict"],
        "verdict_note": triggers["verdict_note"],
    }


# ---------------------------------------------------------------------------
# Report assembly
# ---------------------------------------------------------------------------


def build_report(conn: sqlite3.Connection) -> dict:
    session_ids = fetch_real_session_ids(conn)
    distinct_users = fetch_real_session_user_count(conn, session_ids)

    noun_section = _build_section(
        conn, session_ids, distinct_users,
        NOUN_10K_POS, NOUN_10K_BIN,
        T2_MEAN_ITEMS_DEPLETION, T3_MIN_ITEMS_WITH_3_SHOWN,
    )
    verb_section = _build_section(
        conn, session_ids, distinct_users,
        VERB_10K_POS, VERB_10K_BIN,
        VERB_T2_MEAN_ITEMS_DEPLETION, VERB_T3_MIN_ITEMS_WITH_3_SHOWN,
    )

    noun_s1 = noun_section["signal1_items_per_session"]
    noun_s2 = noun_section["signal2_exposure_per_item"]

    return {
        "report_generated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "db_path": conn.execute("PRAGMA database_list").fetchone()[2],
        "real_session_filter": REAL_SESSION_FILTER,
        "real_session_filter_note": REAL_SESSION_FILTER_NOTE,
        # ---- Backward-compat flat keys (noun/10K) ----
        "summary": {
            "total_real_sessions": len(session_ids),
            "distinct_real_users": distinct_users,
            "sessions_with_noun10k": len(noun_s1),
            "mean_noun10k_per_session": noun_section["summary"]["mean_items_per_session"],
            "active_noun10k_items": len(noun_s2),
        },
        "signal_scope_note": noun_section["signal_scope_note"],
        "signal1_items_per_session": noun_s1,
        "signal2_exposure_per_item": noun_s2,
        "signal3_repeat_rate": noun_section["signal3_repeat_rate"],
        "signal4_correctness": noun_section["signal4_correctness"],
        "trigger_evaluation": noun_section["trigger_evaluation"],
        "verdict": noun_section["verdict"],
        "verdict_note": noun_section["verdict_note"],
        # ---- Nested per-track sections ----
        "noun_10k": noun_section,
        "verb_10k": verb_section,
    }


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def _print_section(section: dict) -> None:
    label = f"{section['pos'].upper()}/{section['bin_name']}"
    tr = section["trigger_evaluation"]
    s = section["summary"]

    print(f"\n  --- {label} ---")
    print(f"  Sessions with {label}: {s['sessions_with_items']}")
    print(f"  Mean {label}/session:  {s['mean_items_per_session']}")
    print(f"  Active {label} items:  {s['active_items']}")

    if not tr["minimum_sample_met"]:
        print(f"  MINIMUM SAMPLE: NOT MET — {tr['verdict_note']}")
    else:
        print(f"  MINIMUM SAMPLE: MET")
        for key in ["T1", "T2", "T3", "T4"]:
            t = tr[key]
            status = "FIRES" if t["fires"] else "ok"
            print(f"    {key} ({t['code']}): {status}")
        if tr.get("broken_items"):
            print(f"  BROKEN ITEMS (pct_correct < 20): {[r['lemma'] for r in tr['broken_items']]}")
        if tr.get("too_easy_items"):
            print(f"  TOO EASY (pct_correct > 85):     {[r['lemma'] for r in tr['too_easy_items']]}")

    print(f"  VERDICT: {section['verdict']}")
    print(f"    {section['verdict_note']}")


def print_summary(report: dict) -> None:
    s = report["summary"]

    print("=" * 60)
    print("VOCAB MONITORING REPORT (noun/10K + verb/10K)")
    print(f"Generated: {report['report_generated_at']}")
    print(f"DB: {report['db_path']}")
    print("=" * 60)
    print(f"\nREAL SESSION FILTER ({report['real_session_filter_note']}):")
    print(f"  {report['real_session_filter']}")
    print(f"\nSAMPLE SIZE:")
    print(f"  Total real sessions:   {s['total_real_sessions']} (need {MINIMUM_SESSIONS})")
    print(f"  Distinct real users:   {s['distinct_real_users']} (need {MINIMUM_USERS})")

    _print_section(report["noun_10k"])
    _print_section(report["verb_10k"])

    print("=" * 60)


def write_json_report(report: dict, output_dir: str) -> str:
    os.makedirs(output_dir, exist_ok=True)
    ts = report["report_generated_at"].replace(":", "").replace("-", "")
    filename = f"noun10k_monitoring_report_{ts}.json"
    path = os.path.join(output_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    return path


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only noun/10K + verb/10K monitoring runner."
    )
    parser.add_argument(
        "--db",
        default="data/lingua_staging.db",
        help="Path to SQLite DB (default: data/lingua_staging.db)",
    )
    parser.add_argument(
        "--output-dir",
        default="diagnostics_exports/",
        help="Directory for JSON report output (default: diagnostics_exports/)",
    )
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Print report to stdout only, do not write JSON file",
    )
    args = parser.parse_args(argv)

    if not os.path.exists(args.db):
        print(f"ERROR: DB not found: {args.db}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    try:
        report = build_report(conn)
    finally:
        conn.close()

    print_summary(report)

    if not args.no_write:
        path = write_json_report(report, args.output_dir)
        print(f"\nJSON report written to: {path}")

    # Exit code based on noun/10K verdict (primary track)
    verdict = report["verdict"]
    if verdict == "INSUFFICIENT_DATA":
        return 0
    elif verdict in ("HOLD", "INVESTIGATE_SIGNAL"):
        return 0
    elif verdict == "PREPARE_NEXT_TRANCHE":
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
