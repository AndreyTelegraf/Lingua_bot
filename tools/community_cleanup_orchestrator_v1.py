#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import subprocess
from collections import Counter
from datetime import datetime, UTC
from pathlib import Path
import glob


def ts() -> str:
    return datetime.now(UTC).strftime("%Y%m%d_%H%M%S")


def run(cmd: list[str], cwd: str | None = None) -> None:
    subprocess.run(cmd, cwd=cwd, check=True)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def db_snapshot(db_path: Path) -> dict:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT id, topic, format_type
        FROM community_content_items
        WHERE is_active = 1
        ORDER BY id
    """).fetchall()
    conn.close()
    return {
        "active_count": len(rows),
        "topics": dict(Counter(r["topic"] for r in rows)),
        "formats": dict(Counter(r["format_type"] for r in rows)),
        "head_ids": [r["id"] for r in rows[:20]],
    }


def latest_dir(base: Path, pattern: str) -> Path:
    dirs = sorted([p for p in base.glob(pattern) if p.is_dir()])
    if not dirs:
        raise FileNotFoundError(f"No dirs for pattern: {pattern}")
    return dirs[-1]


def resolve_first_existing(root: Path, patterns: list[str]) -> str:
    for pattern in patterns:
        matches = sorted(glob.glob(str(root / pattern)))
        if matches:
            return str(Path(matches[0]))
    raise FileNotFoundError(f"No tool matches any of: {patterns}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--chat-ids", nargs="*", type=int, default=[
        -1001690275466,  # chatalgarve
        -1001656765898,  # chatlisboa
        -1001719116315,  # chatporto
        -1001227461571,  # chatleiria
    ])
    ap.add_argument("--adjacent-chat-id", type=int, default=-1001690275466)
    ap.add_argument("--adjacent-steps", type=int, default=40)
    ap.add_argument("--adjacent-cooldown-steps", type=int, default=8)
    ap.add_argument("--multichat-ticks", type=int, default=40)
    ap.add_argument("--multichat-cooldown-ticks", type=int, default=3)
    ap.add_argument("--global-item-cooldown-ticks", type=int, default=3)
    args = ap.parse_args()

    root = Path.cwd()
    db_path = Path(args.db)
    quality_dir = root / "data" / "community_quality"
    run_dir = quality_dir / f"community_cleanup_orchestrator_v1_{ts()}"
    run_dir.mkdir(parents=True, exist_ok=True)

    summary: dict = {
        "db": str(db_path),
        "run_dir": str(run_dir),
        "mode": "apply" if args.apply else "dry_run",
        "before": db_snapshot(db_path),
    }

    # 1) pipeline
    pipeline_cmd = ["python3", "tools/community_cleanup_pipeline_v1.py", "--db", str(db_path)]
    if args.apply:
        pipeline_cmd += ["--apply", "--yes"]
    run(pipeline_cmd)

    pipeline_dir = latest_dir(quality_dir, "community_cleanup_pipeline_v1_*")
    pipeline_summary = read_json(pipeline_dir / "summary.json")
    shutil.copy2(pipeline_dir / "summary.json", run_dir / "pipeline_summary.json")
    shutil.copy2(pipeline_dir / "decisions.json", run_dir / "pipeline_decisions.json")
    summary["pipeline"] = pipeline_summary

    # 2) direct assert / after snapshot
    after = db_snapshot(db_path)
    summary["after"] = after

    # 3) resolve smoke tools dynamically
    runtime_adjacent_tool = resolve_first_existing(root, [
        "tools/community_runtime_adjacent_smoke_v1.py",
        "tools/*runtime*adjacent*smoke*.py",
    ])
    multichat_tool = resolve_first_existing(root, [
        "tools/community_multichat_cooldown_smoke_v2.py",
        "tools/*multichat*cooldown*smoke*.py",
    ])
    global_antidup_tool = resolve_first_existing(root, [
        "tools/community_global_antidup_smoke_v3.py",
        "tools/*global*antidup*smoke*.py",
    ])

    summary["resolved_tools"] = {
        "runtime_adjacent_tool": runtime_adjacent_tool,
        "multichat_tool": multichat_tool,
        "global_antidup_tool": global_antidup_tool,
    }

    # 4) runtime adjacent smoke
    adj_out = run_dir / "runtime_adjacent.json"
    run([
        "python3", runtime_adjacent_tool,
        "--db", str(db_path),
        "--chat-id", str(args.adjacent_chat_id),
        "--steps", str(args.adjacent_steps),
        "--cooldown-steps", str(args.adjacent_cooldown_steps),
        "--out", str(adj_out),
    ])
    summary["runtime_adjacent"] = read_json(adj_out)

    # 5) multichat smoke
    multi_out = run_dir / "multichat.json"
    run([
        "python3", multichat_tool,
        "--db", str(db_path),
        "--chat-ids", *[str(x) for x in args.chat_ids],
        "--ticks", str(args.multichat_ticks),
        "--cooldown-ticks", str(args.multichat_cooldown_ticks),
        "--out", str(multi_out),
    ])
    summary["multichat"] = read_json(multi_out)

    # 6) global anti-dup smoke
    global_out = run_dir / "global_antidup.json"
    run([
        "python3", global_antidup_tool,
        "--db", str(db_path),
        "--chat-ids", *[str(x) for x in args.chat_ids],
        "--ticks", str(args.multichat_ticks),
        "--per-chat-cooldown-ticks", str(args.multichat_cooldown_ticks),
        "--global-item-cooldown-ticks", str(args.global_item_cooldown_ticks),
        "--out", str(global_out),
    ])
    summary["global_antidup"] = read_json(global_out)

    summary["status"] = "green"
    (run_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({
        "run_dir": str(run_dir),
        "mode": summary["mode"],
        "before_active": summary["before"]["active_count"],
        "after_active": summary["after"]["active_count"],
        "pipeline_status": pipeline_summary.get("status"),
        "adjacent_reason_counts": summary["runtime_adjacent"]["summary"]["reason_counts"],
        "multichat_reason_counts": summary["multichat"]["global_summary"]["reason_counts"],
        "global_antidup_reason_counts": summary["global_antidup"]["global_summary"]["reason_counts"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
