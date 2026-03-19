from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, UTC
from pathlib import Path


def run(cmd: list[str], cwd: Path) -> None:
    cp = subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        check=False,
    )
    if cp.returncode != 0:
        raise subprocess.CalledProcessError(
            cp.returncode,
            cmd,
            output="",
            stderr=cp.stderr,
        )


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def now_ts() -> str:
    return datetime.now(UTC).strftime("%Y%m%d_%H%M%S")


def latest_dir(base: Path, pattern: str) -> Path:
    dirs = sorted([p for p in base.glob(pattern) if p.is_dir()])
    if not dirs:
        raise FileNotFoundError(f"No dirs for pattern: {pattern}")
    return dirs[-1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--apply-if-needed", action="store_true")
    ap.add_argument("--restart-staging", action="store_true")
    ap.add_argument("--staging-service", default="lingua-bot-staging.service")
    ap.add_argument("--adjacent-chat-id", type=int, default=-1001690275466)
    ap.add_argument("--chat-ids", nargs="*", type=int, default=[
        -1001690275466,  # chatalgarve
        -1001656765898,  # chatlisboa
        -1001719116315,  # chatporto
        -1001227461571,  # chatleiria
    ])
    args = ap.parse_args()

    root = Path("/home/andrey/Projects/lingua_bot_v2")
    quality_dir = root / "data" / "community_quality"
    run_dir = quality_dir / f"community_cleanup_autorun_v1_{now_ts()}"
    run_dir.mkdir(parents=True, exist_ok=True)

    summary: dict = {
        "db": args.db,
        "run_dir": str(run_dir),
        "mode": "dry_run" if not args.apply_if_needed else "apply_if_needed",
        "steps": [],
    }

    db_path = root / args.db

    applied = False

    # 1) orchestrator dry-run after current state
    run(["python3", "tools/community_cleanup_orchestrator_v1.py", "--db", str(db_path)], cwd=root)
    orch_dir = latest_dir(quality_dir, "community_cleanup_orchestrator_v1_*")
    orch_summary = read_json(orch_dir / "summary.json")
    pipeline_summary = orch_summary["pipeline"]

    summary["pipeline_dry_run"] = pipeline_summary
    summary["orchestrator"] = orch_summary
    summary["steps"].append({
        "step": "pipeline_dry_run",
        "candidate_count": pipeline_summary.get("candidate_count"),
        "run_dir": str(pipeline_summary.get("run_dir")),
    })
    summary["steps"].append({
        "step": "orchestrator_dry_run",
        "run_dir": str(orch_dir),
    })

    # 2) optional apply only when pipeline found candidates
    if args.apply_if_needed and pipeline_summary.get("candidate_count", 0) > 0:
        run([
            "python3", "tools/community_cleanup_pipeline_v1.py",
            "--db", str(db_path),
            "--apply",
            "--yes",
        ], cwd=root)
        pipeline_apply_dir = latest_dir(quality_dir, "community_cleanup_pipeline_v1_*")
        pipeline_apply_summary = read_json(pipeline_apply_dir / "summary.json")
        applied = True
        summary["pipeline_apply"] = pipeline_apply_summary
        summary["steps"].append({
            "step": "pipeline_apply",
            "deactivated_count": pipeline_apply_summary.get("deactivated_count"),
            "run_dir": str(pipeline_apply_dir),
        })

        run(["python3", "tools/community_cleanup_orchestrator_v1.py", "--db", str(db_path)], cwd=root)
        orch_dir = latest_dir(quality_dir, "community_cleanup_orchestrator_v1_*")
        orch_summary = read_json(orch_dir / "summary.json")
        summary["orchestrator_after_apply"] = orch_summary
        summary["steps"].append({
            "step": "orchestrator_post_apply_dry_run",
            "run_dir": str(orch_dir),
        })

    # 4) compact gates
    adjacent = orch_summary["runtime_adjacent"]["summary"]
    multichat = orch_summary["multichat"]["global_summary"]
    global_antidup = orch_summary["global_antidup"]["global_summary"]
    global_results_head = orch_summary["global_antidup"]["results_head"]

    first_tick_ids = sorted({
        row["picked"]["id"]
        for row in global_results_head
        if row.get("tick") == 1 and row.get("picked")
    })

    gates = {
        "pipeline_no_candidates": orch_summary["pipeline"]["candidate_count"] == 0,
        "adjacent_has_fresh": adjacent["reason_counts"].get("candidate_selected_fresh", 0) >= 5,
        "multichat_has_fresh": multichat["reason_counts"].get("candidate_selected_fresh", 0) > 0,
        "global_antidup_has_fresh": global_antidup["reason_counts"].get("candidate_selected_fresh", 0) > 0,
        "global_antidup_diversifies_tick1": len(first_tick_ids) >= min(4, len(args.chat_ids)),
    }

    summary["gates"] = gates
    summary["gate_details"] = {
        "first_tick_unique_ids": first_tick_ids,
        "adjacent_reason_counts": adjacent["reason_counts"],
        "multichat_reason_counts": multichat["reason_counts"],
        "global_antidup_reason_counts": global_antidup["reason_counts"],
        "applied": applied,
    }

    summary["status"] = "green" if all(gates.values()) else "gate_failed"

    # 5) optional restart only on green
    if args.restart_staging and summary["status"] == "green":
        run(["sudo", "systemctl", "restart", args.staging_service], cwd=root)
        run(["systemctl", "is-active", args.staging_service], cwd=root)
        summary["staging_restarted"] = True
    else:
        summary["staging_restarted"] = False

    write_json(run_dir / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if summary["status"] != "green":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
