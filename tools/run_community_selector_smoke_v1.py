from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


def pick_fresh(conn: sqlite3.Connection) -> dict | None:
    row = conn.execute(
        """
        SELECT id, text, format_type, topic
        FROM community_content_items
        WHERE is_active = 1
          AND id NOT IN (
            SELECT item_id
            FROM community_delivery_log
            WHERE item_id IS NOT NULL
          )
        ORDER BY priority ASC, id ASC
        LIMIT 1
        """
    ).fetchone()
    return dict(row) if row else None


def pick_any_active(conn: sqlite3.Connection) -> dict | None:
    row = conn.execute(
        """
        SELECT id, text, format_type, topic
        FROM community_content_items
        WHERE is_active = 1
        ORDER BY priority ASC, id ASC
        LIMIT 1
        """
    ).fetchone()
    return dict(row) if row else None


def ensure_log_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS community_delivery_log (
            id INTEGER PRIMARY KEY,
            item_id INTEGER,
            delivered_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()


def log_pick(conn: sqlite3.Connection, item_id: int) -> None:
    conn.execute(
        "INSERT INTO community_delivery_log (item_id) VALUES (?)",
        (item_id,),
    )
    conn.commit()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--steps", type=int, default=8)
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    ensure_log_table(conn)

    conn.execute("DELETE FROM community_delivery_log")
    conn.commit()

    results = []
    for step in range(1, args.steps + 1):
        row = pick_fresh(conn)
        if row is not None:
            reason = "candidate_selected_fresh"
            picked = row
        else:
            row = pick_any_active(conn)
            if row is None:
                reason = "no_active_candidates"
                picked = None
            else:
                reason = "reuse_after_exhaustion"
                picked = row

        payload = {
            "step": step,
            "reason": reason,
            "picked": picked,
        }
        results.append(payload)

        if picked is not None:
            log_pick(conn, picked["id"])

    out = {
        "steps": args.steps,
        "results": results,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
