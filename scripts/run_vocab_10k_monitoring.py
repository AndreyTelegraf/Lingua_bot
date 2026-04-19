#!/usr/bin/env python3
"""
run_vocab_10k_monitoring.py

Single-command orchestrator for multi-track 10K vocabulary monitoring.
Wraps noun10k_monitoring_runner.build_report() — zero logic duplication.

Produces four artifacts under --output-dir (default: diagnostics_exports/current/):
  vocab_10k_monitoring_report_<ts>.json         — timestamped JSON report
  vocab_10k_monitoring_operator_summary_<ts>.md — timestamped operator summary
  vocab_10k_monitoring_latest.json              — latest copy (overwritten each run)
  vocab_10k_monitoring_latest_summary.md        — latest summary copy

Read-only. Zero DB writes. Zero bank/selector/runtime changes.

USAGE
  python3 scripts/run_vocab_10k_monitoring.py
  python3 scripts/run_vocab_10k_monitoring.py --db data/lingua_staging.db
  python3 scripts/run_vocab_10k_monitoring.py --db data/lingua_staging.db \\
      --output-dir diagnostics_exports/current/
"""
from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(__file__))
from noun10k_monitoring_runner import (
    build_report,
    print_summary,
    write_json_report,
    MINIMUM_SESSIONS,
    MINIMUM_USERS,
    ADVERB_5K_POS,
    ADVERB_5K_BIN,
)

DEFAULT_OUTPUT_DIR = "diagnostics_exports/current"

# Global status derivation: higher priority wins (conservative — surface the
# most-restrictive state so operators don't accidentally skip blocked tracks).
_VERDICT_PRIORITY: dict[str, int] = {
    "HOLD": 0,
    "PREPARE_NEXT_TRANCHE": 1,
    "INSUFFICIENT_DATA": 2,
    "INVESTIGATE_SIGNAL": 3,
}


def derive_global_status(report: dict) -> str:
    """Return the most restrictive verdict across all active tracks."""
    verdicts = [
        report["noun_10k"]["verdict"],
        report["verb_10k"]["verdict"],
        report["adverb_5k"]["verdict"],
    ]
    return max(verdicts, key=lambda v: _VERDICT_PRIORITY.get(v, 0))


# ---------------------------------------------------------------------------
# Policy layer — per-track and global next-action derivation
# ---------------------------------------------------------------------------

_VERDICT_TO_NEXT_ACTION: dict[str, str] = {
    "INSUFFICIENT_DATA": "WAIT_FOR_MORE_REAL_SESSIONS",
    "HOLD": "HOLD_AND_OBSERVE",
    "PREPARE_NEXT_TRANCHE": "PREPARE_NEXT_TRANCHE_ALLOWED",
    "INVESTIGATE_SIGNAL": "INVESTIGATE_REQUIRED",
}

# Higher value = more restrictive = wins in global derivation.
_NEXT_ACTION_PRIORITY: dict[str, int] = {
    "PREPARE_NEXT_TRANCHE_ALLOWED": 0,
    "HOLD_AND_OBSERVE": 1,
    "WAIT_FOR_MORE_REAL_SESSIONS": 2,
    "INVESTIGATE_REQUIRED": 3,
}

_NEXT_ACTION_DESCRIPTION: dict[str, str] = {
    "WAIT_FOR_MORE_REAL_SESSIONS": (
        "Collect more live sessions. Monitor passively. "
        f"Gate requires {MINIMUM_SESSIONS} complete sessions / {MINIMUM_USERS} distinct users."
    ),
    "HOLD_AND_OBSERVE": (
        "All signals nominal. Observe only. "
        "No tranche preparation or activation authorized."
    ),
    "PREPARE_NEXT_TRANCHE_ALLOWED": (
        "Eligible track(s) have fired triggers. "
        "Prepare next tranche activation pack via the staged gate workflow. "
        "Activation itself still requires a separate explicit activation workstream."
    ),
    "INVESTIGATE_REQUIRED": (
        "Broken items detected. Investigate and remediate before any other action. "
        "No preparation or activation authorized until resolved."
    ),
}

# Forbidden actions always enforced regardless of state.
_FORBIDDEN_ALWAYS: list[str] = [
    "DO_NOT_ACTIVATE_ANYTHING",   # activation requires a dedicated gate-check workstream
    "DO_NOT_TOUCH_SELECTOR",
    "DO_NOT_TOUCH_RUNTIME",
    "DO_NOT_MODIFY_NOUN10K",
    "DO_NOT_MODIFY_VERB10K",
    "DO_NOT_MODIFY_ADVERB5K",
]


def derive_track_next_action(verdict: str) -> str:
    """Map a single track's verdict to its operator action code."""
    return _VERDICT_TO_NEXT_ACTION.get(verdict, "HOLD_AND_OBSERVE")


def derive_global_next_action(per_track_actions: dict[str, str]) -> str:
    """Return the most restrictive action across all per-track actions."""
    return max(
        per_track_actions.values(),
        key=lambda a: _NEXT_ACTION_PRIORITY.get(a, 0),
    )


def derive_forbidden_actions(global_next_action: str) -> list[str]:
    """Return the deterministic ordered list of forbidden actions for the current state."""
    forbidden = list(_FORBIDDEN_ALWAYS)
    if global_next_action != "PREPARE_NEXT_TRANCHE_ALLOWED":
        # Tranche prep is unlocked only when the global action explicitly permits it.
        forbidden.insert(1, "DO_NOT_PREPARE_NEW_TRANCHE")
    return forbidden


def build_policy(report: dict, global_status: str) -> dict:
    """Assemble per-track next actions, global next action, and forbidden actions."""
    tracks = {
        "noun_10k": report["noun_10k"]["verdict"],
        "verb_10k": report["verb_10k"]["verdict"],
        "adverb_5k": report["adverb_5k"]["verdict"],
    }
    per_track = {k: derive_track_next_action(v) for k, v in tracks.items()}
    global_action = derive_global_next_action(per_track)
    return {
        "global_status": global_status,
        "per_track_next_actions": per_track,
        "global_next_action": global_action,
        "global_next_action_description": _NEXT_ACTION_DESCRIPTION.get(global_action, ""),
        "forbidden_actions": derive_forbidden_actions(global_action),
    }


def _track_md(section: dict) -> list[str]:
    label = f"{section['pos'].upper()}/{section['bin_name']}"
    s = section["summary"]
    tr = section["trigger_evaluation"]
    verdict = section["verdict"]

    lines = [
        f"### Track: {label}",
        "",
        "| Field | Value |",
        "|-------|-------|",
        f"| Active items | {s['active_items']} |",
        f"| Complete sessions counted | {s['total_real_sessions']} (need {MINIMUM_SESSIONS}) |",
        f"| Distinct users counted | {s['distinct_real_users']} (need {MINIMUM_USERS}) |",
        f"| Minimum sample gate met | {'YES' if tr['minimum_sample_met'] else 'NO'} |",
        f"| Verdict | **{verdict}** |",
        "",
    ]

    if tr["minimum_sample_met"]:
        lines += [
            "**Trigger states:**",
            "",
            "| Trigger | Code | State | Detail |",
            "|---------|------|-------|--------|",
        ]
        for key in ["T1", "T2", "T3", "T4"]:
            t = tr[key]
            state = "**FIRES**" if t["fires"] else "ok"
            if key == "T1":
                detail = (
                    f"mean_repeat_rate={t['mean_repeat_rate']} "
                    f"(fires if >{t['threshold']})"
                )
            elif key == "T2":
                detail = (
                    f"mean_items/session={t['mean_items_per_session']} "
                    f"(fires if <{t['threshold']}, last {t['sessions_evaluated']} sessions)"
                )
            elif key == "T3":
                detail = (
                    f"items_shown≥3: {t['items_with_shown_gte_3']}/{t['total_active_items']} "
                    f"(fires if <{t['threshold']})"
                )
            else:
                detail = (
                    f"max_shown={t['max_sessions_shown']}, "
                    f"pool_median={t['pool_median_sessions_shown']}"
                )
            lines.append(f"| {key} | {t['code']} | {state} | {detail} |")
        lines.append("")

        if tr.get("broken_items"):
            lemmas = [r["lemma"] for r in tr["broken_items"]]
            lines.append(f"**BROKEN ITEMS (pct_correct < 20):** {lemmas}")
            lines.append("")
        if tr.get("too_easy_items"):
            lemmas = [r["lemma"] for r in tr["too_easy_items"]]
            lines.append(f"**TOO EASY (pct_correct > 85):** {lemmas}")
            lines.append("")
    else:
        lines += [
            f"Minimum sample gate not met: {tr['verdict_note']}",
            "",
        ]

    if verdict == "INVESTIGATE_SIGNAL":
        next_action = "Investigate broken items. Fix distractor or content issues before any action."
        do_not = "DO NOT activate any tranche for this track until broken items are resolved."
    elif verdict == "PREPARE_NEXT_TRANCHE":
        next_action = "Review activation execution plan. Prepare next tranche activation pack."
        do_not = "DO NOT activate without completing the tranche prep checklist and stage gate review."
    elif verdict == "INSUFFICIENT_DATA":
        next_action = "Continue collecting live session data. Rerun monitoring after more sessions accumulate."
        do_not = "DO NOT prepare or activate any tranche for this track."
    else:
        next_action = "Continue monitoring. No activation prep authorized at this time."
        do_not = "DO NOT prepare or activate any tranche for this track."

    lines += [
        f"**Next allowed action:** {next_action}",
        "",
        f"> {do_not}",
        "",
    ]
    return lines


def build_operator_summary(
    report: dict,
    global_status: str,
    json_path: str,
    policy: dict | None = None,
) -> str:
    ts = report["report_generated_at"]
    db = report.get("db_path", "unknown")
    s = report["summary"]
    noun_s = report["noun_10k"]
    verb_s = report["verb_10k"]
    adverb_s = report["adverb_5k"]

    trigger_eligible_tracks = [
        f"{t['pos'].upper()}/{t['bin_name']}"
        for t in [noun_s, verb_s, adverb_s]
        if t["verdict"] == "PREPARE_NEXT_TRANCHE"
    ]
    any_trigger_eligible = bool(trigger_eligible_tracks)
    tranche_prep_authorized = any_trigger_eligible and global_status == "PREPARE_NEXT_TRANCHE"

    if global_status == "INVESTIGATE_SIGNAL":
        next_step = "Identify broken items across all tracks and remediate before any activation."
    elif global_status == "PREPARE_NEXT_TRANCHE":
        next_step = (
            f"Prepare next tranche activation pack for: {', '.join(trigger_eligible_tracks)}. "
            "Follow the staged gate workflow."
        )
    elif global_status == "INSUFFICIENT_DATA":
        next_step = (
            f"Collect more live sessions. Currently {s['total_real_sessions']} sessions, "
            f"{s['distinct_real_users']} users. "
            f"Gate requires {MINIMUM_SESSIONS} sessions / {MINIMUM_USERS} users."
        )
    else:
        next_step = "No action required. Continue monitoring. Rerun when more sessions accumulate."

    lines: list[str] = [
        "# Vocab Monitoring — Operator Summary (noun/10K · verb/10K · adverb/5K)",
        "",
        f"**Generated:** {ts}",
        f"**DB:** {db}",
        f"**JSON report:** {json_path}",
        "",
        "---",
        "",
        "## Global Status",
        "",
        "| Field | Value |",
        "|-------|-------|",
        f"| Overall status | **{global_status}** |",
        f"| Any track trigger-eligible | {'YES — ' + ', '.join(trigger_eligible_tracks) if any_trigger_eligible else 'NO'} |",
        f"| Any tranche prep/apply authorized | {'YES' if tranche_prep_authorized else 'NO'} |",
        f"| Total real sessions | {s['total_real_sessions']} |",
        f"| Distinct real users | {s['distinct_real_users']} |",
        "",
        f"**Exact next step:** {next_step}",
        "",
        "---",
        "",
    ]

    # Policy sections (present when policy is provided)
    if policy:
        global_action = policy["global_next_action"]
        action_desc = policy.get("global_next_action_description", "")
        forbidden = policy["forbidden_actions"]
        per_track = policy["per_track_next_actions"]

        lines += [
            "## Authorized Now",
            "",
            f"**Global action:** `{global_action}`",
            "",
            f"{action_desc}",
            "",
            "**Per-track:**",
            "",
        ]
        for track_key, action in per_track.items():
            track_label = track_key.replace("_", "/").upper()
            lines.append(f"- {track_label}: `{action}`")
        lines += [
            "",
            "---",
            "",
            "## Forbidden Now",
            "",
        ]
        for item in forbidden:
            lines.append(f"- `{item}`")
        lines += [
            "",
            "---",
            "",
        ]

    lines += [
        "## Per-Track Decision Table",
        "",
    ]

    lines += _track_md(noun_s)
    lines += _track_md(verb_s)
    lines += _track_md(adverb_s)

    lines += [
        "---",
        "",
        "*Generated by scripts/run_vocab_10k_monitoring.py — read-only, no DB writes.*",
    ]

    return "\n".join(lines) + "\n"


_CURRENT_POSITION: dict[str, str] = {
    "INSUFFICIENT_DATA": (
        "The monitoring system is tracking three active vocab pools: noun/10K, verb/10K, and "
        "adverb/5K. All pools are in observation-only mode. The real-session sample has not yet "
        "reached the minimum gate ({min_sessions} complete sessions from {min_users} distinct "
        "users). No bank-growth work — tranche prep, activation, or any pool modification — is "
        "authorized until the gate is met and signals are evaluated."
    ),
    "HOLD": (
        "The monitoring system is tracking three active vocab pools: noun/10K, verb/10K, and "
        "adverb/5K. The minimum sample gate has been met. All signals are nominal; no triggers "
        "have fired. The system is in hold-and-observe mode. No tranche preparation or activation "
        "is authorized at this time. Continue collecting sessions and rerun monitoring periodically."
    ),
    "PREPARE_NEXT_TRANCHE": (
        "The monitoring system is tracking three active vocab pools: noun/10K, verb/10K, and "
        "adverb/5K. One or more tracks have fired activation triggers. Tranche preparation is "
        "authorized for eligible tracks only. Activation itself still requires a separate "
        "gate-check workstream. No direct activation may occur in the same session as tranche prep."
    ),
    "INVESTIGATE_SIGNAL": (
        "The monitoring system is tracking three active vocab pools: noun/10K, verb/10K, and "
        "adverb/5K. One or more tracks have items with anomalous correctness rates (pct_correct "
        "< 20). Broken items must be investigated and remediated before any other bank-growth "
        "work. No preparation or activation is authorized until broken items are resolved."
    ),
}


def build_status_snapshot(
    report: dict,
    global_status: str,
    policy: dict,
) -> str:
    """Build a compact operator-facing status snapshot for handoff/next-chat context.

    Derived entirely from the existing report and policy dicts — no new DB queries.
    """
    ts = report["report_generated_at"]
    db = report.get("db_path", "unknown")
    s = report["summary"]
    total_sessions = s["total_real_sessions"]
    distinct_users = s["distinct_real_users"]

    track_keys = [("noun_10k", "noun/10K"), ("verb_10k", "verb/10K"), ("adverb_5k", "adverb/5K")]
    per_track_actions = policy["per_track_next_actions"]
    global_action = policy["global_next_action"]
    forbidden = policy["forbidden_actions"]
    tranche_authorized = global_action == "PREPARE_NEXT_TRANCHE_ALLOWED"

    # ---- EXACT NEXT STEP derivation (deterministic) ----
    if global_status == "INSUFFICIENT_DATA":
        exact_next_step = (
            f"Rerun monitoring after >={MINIMUM_SESSIONS} complete sessions from "
            f">={MINIMUM_USERS} users. Currently {total_sessions} sessions, {distinct_users} users."
        )
    elif global_status == "INVESTIGATE_SIGNAL":
        broken = []
        for tk, _ in track_keys:
            tr = report[tk].get("trigger_evaluation", {})
            for item in tr.get("broken_items", []):
                broken.append(f"{report[tk]['pos']}/{report[tk]['bin_name']}: {item['lemma']}")
        exact_next_step = f"Investigate broken items: {', '.join(broken)}. Fix before any action."
    elif global_status == "PREPARE_NEXT_TRANCHE":
        eligible = [
            label for tk, label in track_keys
            if report[tk]["verdict"] == "PREPARE_NEXT_TRANCHE"
        ]
        exact_next_step = (
            f"Prepare next tranche activation pack for: {', '.join(eligible)}. "
            "Follow the staged gate workflow. Activation requires a separate workstream."
        )
    else:
        exact_next_step = (
            "Continue monitoring. No action required. "
            "Rerun when more sessions accumulate."
        )

    # ---- Current position paragraph ----
    template = _CURRENT_POSITION.get(global_status, _CURRENT_POSITION["HOLD"])
    current_position = template.format(
        min_sessions=MINIMUM_SESSIONS, min_users=MINIMUM_USERS
    )

    # ---- Build markdown ----
    lines = [
        "# Vocab Monitoring — Status Snapshot",
        "",
        f"**Generated:** {ts}",
        f"**DB:** {db}",
        "",
        "---",
        "",
        "## 1. Track Summary",
        "",
        "| Track | Active items | Verdict | Sessions counted | Users counted | Gate met | Next action |",
        "|-------|-------------|---------|-----------------|---------------|----------|-------------|",
    ]
    for tk, label in track_keys:
        sec = report[tk]
        sec_s = sec["summary"]
        tr = sec["trigger_evaluation"]
        gate_met = "YES" if tr.get("minimum_sample_met") else "NO"
        action = per_track_actions.get(tk, "—")
        lines.append(
            f"| {label} | {sec_s['active_items']} | {sec['verdict']} "
            f"| {total_sessions} | {distinct_users} | {gate_met} | `{action}` |"
        )

    lines += [
        "",
        "---",
        "",
        "## 2. Global Summary",
        "",
        "| Field | Value |",
        "|-------|-------|",
        f"| Global status | **{global_status}** |",
        f"| Global next action | `{global_action}` |",
        f"| Any tranche/apply authorized | {'**YES**' if tranche_authorized else 'NO'} |",
        "",
        "**Forbidden actions:**",
        "",
    ]
    for item in forbidden:
        lines.append(f"- `{item}`")

    lines += [
        "",
        "---",
        "",
        "## 3. Current Position",
        "",
        current_position,
        "",
        "---",
        "",
        "## 4. Exact Next Step",
        "",
        f"> {exact_next_step}",
        "",
        "---",
        "",
        "*Read-only snapshot. No DB writes. Generated by scripts/run_vocab_10k_monitoring.py.*",
    ]

    return "\n".join(lines) + "\n"


def _write_text(content: str, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Multi-track 10K monitoring orchestrator. Read-only."
    )
    parser.add_argument(
        "--db",
        default="data/lingua_staging.db",
        help="Path to SQLite DB (default: data/lingua_staging.db)",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory (default: {DEFAULT_OUTPUT_DIR})",
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

    global_status = derive_global_status(report)
    policy = build_policy(report, global_status)

    # Inject policy into report dict so JSON is self-contained.
    report["policy"] = policy

    # Timestamped JSON
    json_path = write_json_report(report, args.output_dir)

    # Timestamped operator summary
    ts_tag = report["report_generated_at"].replace(":", "").replace("-", "")
    summary_content = build_operator_summary(report, global_status, json_path, policy=policy)
    md_filename = f"vocab_10k_monitoring_operator_summary_{ts_tag}.md"
    md_path = os.path.join(args.output_dir, md_filename)
    _write_text(summary_content, md_path)

    # Status snapshot
    snapshot_content = build_status_snapshot(report, global_status, policy)
    snapshot_filename = f"vocab_10k_status_snapshot_{ts_tag}.md"
    snapshot_path = os.path.join(args.output_dir, snapshot_filename)
    _write_text(snapshot_content, snapshot_path)
    snapshot_latest = os.path.join(args.output_dir, "vocab_10k_status_snapshot_latest.md")
    shutil.copy2(snapshot_path, snapshot_latest)

    # Latest copies (overwritten each run)
    latest_json = os.path.join(args.output_dir, "vocab_10k_monitoring_latest.json")
    latest_md = os.path.join(args.output_dir, "vocab_10k_monitoring_latest_summary.md")
    shutil.copy2(json_path, latest_json)
    shutil.copy2(md_path, latest_md)

    print(f"\nGLOBAL STATUS:      {global_status}")
    print(f"GLOBAL NEXT ACTION: {policy['global_next_action']}")
    print(f"\nArtifacts written to: {args.output_dir}")
    print(f"  {os.path.basename(json_path)}")
    print(f"  {os.path.basename(md_path)}")
    print(f"  {os.path.basename(snapshot_path)}")
    print(f"  vocab_10k_monitoring_latest.json        [latest]")
    print(f"  vocab_10k_monitoring_latest_summary.md  [latest]")
    print(f"  vocab_10k_status_snapshot_latest.md     [latest]")

    return 0


if __name__ == "__main__":
    sys.exit(main())
