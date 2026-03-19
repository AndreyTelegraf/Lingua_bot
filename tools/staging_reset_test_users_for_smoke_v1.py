from __future__ import annotations
import json
import shutil
import sqlite3
from datetime import datetime, UTC
from pathlib import Path

ROOT = Path("/home/andrey/Projects/lingua_bot_v2")
DB = ROOT / "data/lingua_staging.db"
OUT_DIR = ROOT / "data/master_source_v1/processed/staging_reset_test_users_for_smoke_v1"
OUT_DIR.mkdir(parents=True, exist_ok=True)

if not DB.exists():
    raise SystemExit(f"DB not found: {DB}")

backup = OUT_DIR / f"lingua_staging.before_reset_test_users_for_smoke_v1.{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.db"
shutil.copy2(DB, backup)

tables_to_clear_in_order = [
    "vocab_answers",
    "vocab_attempt_events",
    "vocab_attempts",
    "vocab_item_exposure",
    "vocab_result_snapshots",
    "vocab_selector_state",
    "mode_results",
    "mode_runs",
    "user_progress_events",
    "user_assessment_profile",
    "user_mode_baselines",
    "user_mode_priors",
    "user_profiles",
    "fsm_runtime_state",
    "users",
]

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

existing_tables = {
    r["name"] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
}

missing = [t for t in tables_to_clear_in_order if t not in existing_tables]
present = [t for t in tables_to_clear_in_order if t in existing_tables]

pre_counts = {}
for t in present:
    pre_counts[t] = cur.execute(f"SELECT COUNT(*) AS c FROM {t}").fetchone()["c"]

# capture active bank invariants before reset
cols = [dict(r) for r in cur.execute("PRAGMA table_info(vocab_items)").fetchall()]
col_names = [r["name"] for r in cols]
active_col = "is_active" if "is_active" in col_names else "active"
active_total_before = cur.execute(f"SELECT COUNT(*) AS c FROM vocab_items WHERE {active_col}=1").fetchone()["c"]

cur.execute("PRAGMA foreign_keys = OFF")
for t in present:
    cur.execute(f"DELETE FROM {t}")

if "sqlite_sequence" in existing_tables:
    for t in present:
        try:
            cur.execute("DELETE FROM sqlite_sequence WHERE name = ?", (t,))
        except Exception:
            pass

cur.execute("PRAGMA foreign_keys = ON")
conn.commit()

post_counts = {}
for t in present:
    post_counts[t] = cur.execute(f"SELECT COUNT(*) AS c FROM {t}").fetchone()["c"]

active_total_after = cur.execute(f"SELECT COUNT(*) AS c FROM vocab_items WHERE {active_col}=1").fetchone()["c"]

summary = {
    "db": str(DB),
    "backup": str(backup),
    "tables_requested": tables_to_clear_in_order,
    "tables_present": present,
    "tables_missing": missing,
    "pre_counts": pre_counts,
    "post_counts": post_counts,
    "active_total_before": active_total_before,
    "active_total_after": active_total_after,
    "utc_timestamp": datetime.now(UTC).isoformat(),
}
(OUT_DIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False, indent=2))

conn.close()
