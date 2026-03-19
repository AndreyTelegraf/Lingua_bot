#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

ROOT = Path("/home/andrey/Projects/lingua_bot_v2")
DEFAULT_DB = ROOT / "data/lingua_staging.db"
OUT_BASE = ROOT / "data" / "community_operational_guardrail_v1"


class GuardrailError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def ts() -> str:
    return datetime.now(UTC).strftime("%Y%m%d_%H%M%S")


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def run_cmd(cmd: list[str], cwd: Path = ROOT) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=False)


def git_head() -> str:
    cp = run_cmd(["git", "rev-parse", "--short", "HEAD"])
    return cp.stdout.strip() if cp.returncode == 0 else "unknown"


def write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if not text:
        raise GuardrailError("empty process output, expected json")
    try:
        obj = json.loads(text)
    except Exception as e:
        raise GuardrailError(f"failed to parse json output: {e}") from e
    if not isinstance(obj, dict):
        raise GuardrailError("top-level json must be object")
    return obj


def nonneg_int(v: Any, name: str) -> None:
    if not isinstance(v, int) or v < 0:
        raise GuardrailError(f"{name} must be non-negative int, got {v!r}")


def must_bool(v: Any, name: str) -> None:
    if not isinstance(v, bool):
        raise GuardrailError(f"{name} must be bool, got {v!r}")


def must_str(v: Any, name: str) -> None:
    if not isinstance(v, str) or not v:
        raise GuardrailError(f"{name} must be non-empty str, got {v!r}")


def validate_pipeline_summary(summary: dict[str, Any]) -> None:
    for key in ["db", "run_dir", "mode", "before", "duplicate_family_count", "theme_group_count", "candidate_count", "decisions"]:
        if key not in summary:
            raise GuardrailError(f"pipeline summary missing field: {key}")

    must_str(summary["db"], "pipeline.db")
    must_str(summary["run_dir"], "pipeline.run_dir")
    if summary["mode"] not in {"dry_run", "apply"}:
        raise GuardrailError(f"pipeline.mode invalid: {summary['mode']!r}")

    before = summary["before"]
    if not isinstance(before, dict):
        raise GuardrailError("pipeline.before must be object")
    if "active_count" not in before:
        raise GuardrailError("pipeline.before missing active_count")
    nonneg_int(before["active_count"], "pipeline.before.active_count")

    nonneg_int(summary["duplicate_family_count"], "pipeline.duplicate_family_count")
    nonneg_int(summary["theme_group_count"], "pipeline.theme_group_count")
    nonneg_int(summary["candidate_count"], "pipeline.candidate_count")

    decisions = summary["decisions"]
    if not isinstance(decisions, list):
        raise GuardrailError("pipeline.decisions must be list")

    if summary["candidate_count"] != len(summary.get("candidate_ids", [])):
        if "candidate_ids" in summary:
            raise GuardrailError("pipeline candidate_count != len(candidate_ids)")

    if summary["candidate_count"] == 0 and decisions != []:
        raise GuardrailError("pipeline.decisions must be [] when candidate_count == 0")


def validate_autorun_summary(summary: dict[str, Any]) -> None:
    for key in ["db", "run_dir", "mode", "steps", "pipeline_dry_run", "orchestrator", "gates", "gate_details", "status", "staging_restarted"]:
        if key not in summary:
            raise GuardrailError(f"autorun summary missing field: {key}")

    must_str(summary["db"], "autorun.db")
    must_str(summary["run_dir"], "autorun.run_dir")
    if summary["mode"] not in {"dry_run", "apply_if_needed"}:
        raise GuardrailError(f"autorun.mode invalid: {summary['mode']!r}")
    if summary["status"] not in {"green", "gate_failed"}:
        raise GuardrailError(f"autorun.status invalid: {summary['status']!r}")
    if not isinstance(summary["steps"], list):
        raise GuardrailError("autorun.steps must be list")
    must_bool(summary["staging_restarted"], "autorun.staging_restarted")

    gates = summary["gates"]
    if not isinstance(gates, dict):
        raise GuardrailError("autorun.gates must be object")

    for key in [
        "pipeline_no_candidates",
        "adjacent_has_fresh",
        "multichat_has_fresh",
        "global_antidup_has_fresh",
        "global_antidup_diversifies_tick1",
    ]:
        if key not in gates:
            raise GuardrailError(f"autorun.gates missing field: {key}")
        must_bool(gates[key], f"autorun.gates.{key}")


def service_is_active(unit: str) -> bool:
    cp = run_cmd(["systemctl", "is-active", unit])
    return cp.returncode == 0 and cp.stdout.strip() == "active"


def run_pipeline(db: Path, mode: str) -> tuple[dict[str, Any], dict[str, Any]]:
    cmd = ["python3", "tools/community_cleanup_pipeline_v1.py", "--db", str(db)]
    if mode == "apply-if-needed":
        cmd += ["--apply", "--yes"]

    cp = run_cmd(cmd)
    step = {
        "cmd": cp.args,
        "returncode": cp.returncode,
        "stdout": cp.stdout,
        "stderr": cp.stderr,
    }
    if cp.returncode != 0:
        raise GuardrailError(f"pipeline failed: {cp.stderr or cp.stdout}")

    summary = extract_json(cp.stdout)
    validate_pipeline_summary(summary)
    return summary, step


def run_autorun(db: Path, mode: str, restart_staging: bool, staging_service: str) -> tuple[dict[str, Any], dict[str, Any]]:
    cmd = ["python3", "tools/community_cleanup_autorun_v1.py", "--db", str(db)]
    if mode == "apply-if-needed":
        cmd.append("--apply-if-needed")
    if restart_staging:
        cmd += ["--restart-staging", "--staging-service", staging_service]

    cp = run_cmd(cmd)
    step = {
        "cmd": cp.args,
        "returncode": cp.returncode,
        "stdout": cp.stdout,
        "stderr": cp.stderr,
    }
    if cp.returncode != 0:
        raise GuardrailError(f"autorun failed: {cp.stderr or cp.stdout}")

    summary = extract_json(cp.stdout)
    validate_autorun_summary(summary)
    return summary, step


def summarize_status(pipeline: dict[str, Any], autorun: dict[str, Any], requested_restart: bool, service_active: bool) -> tuple[str, list[str], list[str]]:
    hard_failures: list[str] = []
    soft_warnings: list[str] = []

    gates = autorun["gates"]

    if autorun["status"] != "green":
        hard_failures.append("autorun_status_not_green")

    if not gates["adjacent_has_fresh"]:
        hard_failures.append("adjacent_has_fresh_false")
    if not gates["multichat_has_fresh"]:
        hard_failures.append("multichat_has_fresh_false")
    if not gates["global_antidup_has_fresh"]:
        hard_failures.append("global_antidup_has_fresh_false")
    if not gates["global_antidup_diversifies_tick1"]:
        hard_failures.append("global_antidup_diversifies_tick1_false")

    if pipeline["candidate_count"] > 0 and autorun["mode"] == "dry_run":
        soft_warnings.append("cleanup_candidates_present_but_not_applied")

    if requested_restart and not autorun["staging_restarted"]:
        hard_failures.append("restart_requested_but_not_confirmed_by_autorun")
    if requested_restart and not service_active:
        hard_failures.append("service_not_active_after_restart")

    status = "green"
    if hard_failures:
        status = "red"
    elif soft_warnings:
        status = "yellow"

    return status, hard_failures, soft_warnings


def execute_once(mode: str, db: Path, restart_staging: bool, staging_service: str) -> tuple[dict[str, Any], Path]:
    run_dir = ensure_dir(OUT_BASE / f"run_{ts()}")
    started_at = now_iso()

    pipeline_summary, pipeline_step = run_pipeline(db=db, mode=mode)
    autorun_summary, autorun_step = run_autorun(
        db=db,
        mode=mode,
        restart_staging=restart_staging,
        staging_service=staging_service,
    )

    service_active = True
    if restart_staging:
        service_active = service_is_active(staging_service)

    status, hard_failures, soft_warnings = summarize_status(
        pipeline=pipeline_summary,
        autorun=autorun_summary,
        requested_restart=restart_staging,
        service_active=service_active,
    )

    summary = {
        "run_id": run_dir.name,
        "started_at_utc": started_at,
        "finished_at_utc": now_iso(),
        "git_head": git_head(),
        "mode": mode,
        "db": str(db),
        "restart_staging_requested": restart_staging,
        "staging_service": staging_service,
        "status": status,
        "hard_failures": hard_failures,
        "soft_warnings": soft_warnings,
        "checks": {
            "service_active": service_active,
        },
        "pipeline_summary": pipeline_summary,
        "autorun_summary": autorun_summary,
        "steps": {
            "pipeline": pipeline_step,
            "autorun": autorun_step,
        },
    }

    write_json(run_dir / "guardrail_summary.json", summary)
    return summary, run_dir


def execute_soak(db: Path, runs: int, interval_sec: int, restart_first_run: bool, staging_service: str) -> int:
    soak_dir = ensure_dir(OUT_BASE / f"soak_{ts()}")
    records: list[dict[str, Any]] = []

    for idx in range(runs):
        restart = restart_first_run and idx == 0
        try:
            summary, run_dir = execute_once(
                mode="verify",
                db=db,
                restart_staging=restart,
                staging_service=staging_service,
            )
            records.append({
                "index": idx + 1,
                "status": summary["status"],
                "run_dir": str(run_dir),
                "candidate_count": summary["pipeline_summary"]["candidate_count"],
                "hard_failures": summary["hard_failures"],
                "soft_warnings": summary["soft_warnings"],
            })
        except Exception as e:
            records.append({
                "index": idx + 1,
                "status": "red",
                "error": str(e),
            })

        if idx < runs - 1:
            time.sleep(interval_sec)

    green_runs = sum(1 for r in records if r["status"] == "green")
    yellow_runs = sum(1 for r in records if r["status"] == "yellow")
    red_runs = sum(1 for r in records if r["status"] == "red")

    soak_summary = {
        "soak_id": soak_dir.name,
        "finished_at_utc": now_iso(),
        "db": str(db),
        "runs_requested": runs,
        "interval_sec": interval_sec,
        "green_runs": green_runs,
        "yellow_runs": yellow_runs,
        "red_runs": red_runs,
        "all_green": red_runs == 0 and yellow_runs == 0,
        "records": records,
    }

    write_json(soak_dir / "soak_summary.json", soak_summary)
    print(json.dumps(soak_summary, ensure_ascii=False, indent=2))
    return 0 if soak_summary["all_green"] else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["verify", "apply-if-needed", "soak"], required=True)
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--restart-staging", action="store_true")
    ap.add_argument("--restart-staging-first-run", action="store_true")
    ap.add_argument("--staging-service", default="lingua-bot-staging.service")
    ap.add_argument("--soak-runs", type=int, default=6)
    ap.add_argument("--soak-interval-sec", type=int, default=300)
    args = ap.parse_args()

    db = Path(args.db)
    ensure_dir(OUT_BASE)

    try:
        if args.mode == "soak":
            return execute_soak(
                db=db,
                runs=args.soak_runs,
                interval_sec=args.soak_interval_sec,
                restart_first_run=args.restart_staging_first_run,
                staging_service=args.staging_service,
            )

        summary, run_dir = execute_once(
            mode=args.mode,
            db=db,
            restart_staging=args.restart_staging,
            staging_service=args.staging_service,
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        print(f"\nARTIFACT_DIR={run_dir}")
        return 0 if summary["status"] != "red" else 1

    except Exception as e:
        failure = {
            "status": "red",
            "error": str(e),
            "mode": args.mode,
            "git_head": git_head(),
            "timestamp_utc": now_iso(),
        }
        print(json.dumps(failure, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
