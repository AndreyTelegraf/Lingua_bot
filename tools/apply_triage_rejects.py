from __future__ import annotations

import csv
import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

BASE = Path("/home/andrey/Projects/lingua_bot_v2")
DB = BASE / "data/lingua_staging.db"
TS = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
OUT_DIR = BASE / "artifacts" / f"triage_apply_{TS}"
BACKUP = OUT_DIR / f"lingua_staging_before_triage_apply_{TS}.db"
CSV_PATH = BASE / "tools" / "active_bank_manual_audit_heuristic_marked.csv"

def q(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    cur = conn.execute(sql, params)
    return cur.fetchall()

def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DB, BACKUP)

    with CSV_PATH.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))

    reject_rows = [r for r in rows if (r.get("triage_status") or "").strip().upper() == "REJECT"]
    reject_ids = sorted({int(r["id"]) for r in reject_rows if str(r.get("id", "")).isdigit()})

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    before_active = q(conn, "SELECT COUNT(*) AS n FROM vocab_items WHERE is_active = 1")[0]["n"]

    applied_remove = 0
    already_inactive = 0
    missing_item = 0
    reject_preview: list[dict] = []

    for item_id in reject_ids:
        row = conn.execute(
            "SELECT id, lemma, correct_answer, pos, bin_name, is_active FROM vocab_items WHERE id = ?",
            (item_id,),
        ).fetchone()
        if row is None:
            missing_item += 1
            continue
        if int(row["is_active"] or 0) != 1:
            already_inactive += 1
            continue

        conn.execute("UPDATE vocab_items SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (item_id,))
        applied_remove += 1
        reject_preview.append(
            {
                "id": row["id"],
                "lemma": row["lemma"],
                "correct_answer": row["correct_answer"],
                "pos": row["pos"],
                "bin_name": row["bin_name"],
            }
        )

    conn.commit()

    after_active = q(conn, "SELECT COUNT(*) AS n FROM vocab_items WHERE is_active = 1")[0]["n"]

    ready_pos = q(
        conn,
        """
        WITH ready_items AS (
            SELECT vc.item_id
            FROM vocab_choices vc
            GROUP BY vc.item_id
            HAVING COUNT(*) = 6
        )
        SELECT vi.pos AS pos, COUNT(*) AS n
        FROM vocab_items vi
        JOIN ready_items ri ON ri.item_id = vi.id
        WHERE vi.is_active = 1
        GROUP BY vi.pos
        ORDER BY n DESC
        """,
    )
    ready_bin = q(
        conn,
        """
        WITH ready_items AS (
            SELECT vc.item_id
            FROM vocab_choices vc
            GROUP BY vc.item_id
            HAVING COUNT(*) = 6
        )
        SELECT vi.bin_name AS bin_name, COUNT(*) AS n
        FROM vocab_items vi
        JOIN ready_items ri ON ri.item_id = vi.id
        WHERE vi.is_active = 1
        GROUP BY vi.bin_name
        ORDER BY n DESC
        """,
    )

    summary = {
        "source_csv": str(CSV_PATH),
        "output_dir": str(OUT_DIR),
        "db_backup": str(BACKUP),
        "csv_rows": len(rows),
        "reject_rows_in_csv": len(reject_rows),
        "reject_ids": reject_ids,
        "applied_remove": applied_remove,
        "already_inactive": already_inactive,
        "missing_item": missing_item,
        "active_before": before_active,
        "active_after": after_active,
        "ready_items_by_pos_after": {str(r["pos"]): int(r["n"]) for r in ready_pos},
        "ready_items_by_bin_after": {str(r["bin_name"]): int(r["n"]) for r in ready_bin},
    }

    (OUT_DIR / "apply_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    with (OUT_DIR / "reject_preview.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["id", "lemma", "correct_answer", "pos", "bin_name"])
        writer.writeheader()
        writer.writerows(reject_preview)

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    conn.close()

if __name__ == "__main__":
    main()
