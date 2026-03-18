from __future__ import annotations

import argparse
import json
import re
import sqlite3
from collections import Counter
from pathlib import Path


def first_words(text: str, n: int) -> str:
    words = re.findall(r"[A-Za-zÀ-ÿА-Яа-яЁё0-9-]+", text.lower())
    return " ".join(words[:n])


def ensure_smoke_log_table(conn: sqlite3.Connection, table: str) -> None:
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {table} (
            id INTEGER PRIMARY KEY,
            chat_id INTEGER NOT NULL,
            item_id INTEGER,
            delivered_at_step INTEGER NOT NULL
        )
        """
    )
    conn.commit()


def reset_smoke_log_table(conn: sqlite3.Connection, table: str) -> None:
    conn.execute(f"DELETE FROM {table}")
    conn.commit()


def cooldown_active(
    conn: sqlite3.Connection,
    *,
    table: str,
    chat_id: int,
    current_step: int,
    cooldown_steps: int,
) -> bool:
    row = conn.execute(
        f"""
        SELECT MAX(delivered_at_step)
        FROM {table}
        WHERE chat_id = ?
        """,
        (chat_id,),
    ).fetchone()
    last_step = row[0]
    if last_step is None:
        return False
    return (current_step - last_step) < cooldown_steps


def pick_fresh(
    conn: sqlite3.Connection,
    *,
    log_table: str,
) -> dict | None:
    row = conn.execute(
        f"""
        SELECT id, text, format_type, topic, priority
        FROM community_content_items
        WHERE is_active = 1
          AND id NOT IN (
            SELECT item_id
            FROM {log_table}
            WHERE item_id IS NOT NULL
          )
        ORDER BY priority ASC, id ASC
        LIMIT 1
        """
    ).fetchone()
    return dict(row) if row else None


def pick_reuse(
    conn: sqlite3.Connection,
) -> dict | None:
    row = conn.execute(
        """
        SELECT id, text, format_type, topic, priority
        FROM community_content_items
        WHERE is_active = 1
        ORDER BY priority ASC, id ASC
        LIMIT 1
        """
    ).fetchone()
    return dict(row) if row else None


def log_pick(
    conn: sqlite3.Connection,
    *,
    table: str,
    chat_id: int,
    item_id: int,
    step: int,
) -> None:
    conn.execute(
        f"""
        INSERT INTO {table} (chat_id, item_id, delivered_at_step)
        VALUES (?, ?, ?)
        """,
        (chat_id, item_id, step),
    )
    conn.commit()


def analyze(results: list[dict]) -> dict:
    picked = [r["picked"] for r in results if r.get("picked")]
    texts = [x["text"] for x in picked]
    reasons = Counter(r["reason"] for r in results)
    topics = Counter(x["topic"] for x in picked)
    formats = Counter(x["format_type"] for x in picked)
    first1 = Counter(first_words(t, 1) for t in texts)
    first2 = Counter(first_words(t, 2) for t in texts)
    first3 = Counter(first_words(t, 3) for t in texts)

    return {
        "reason_counts": dict(reasons),
        "picked_count": len(picked),
        "topics": dict(topics),
        "formats": dict(formats),
        "first1": dict(first1),
        "first2": dict(first2),
        "first3": dict(first3),
        "length_min": min((len(t) for t in texts), default=0),
        "length_max": max((len(t) for t in texts), default=0),
        "length_avg": round(sum(len(t) for t in texts) / len(texts), 2) if texts else 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--chat-id", type=int, required=True)
    parser.add_argument("--steps", type=int, default=30)
    parser.add_argument("--cooldown-steps", type=int, default=1)
    parser.add_argument("--log-table", default="community_delivery_log_smoke_v1")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row

    ensure_smoke_log_table(conn, args.log_table)
    reset_smoke_log_table(conn, args.log_table)

    results: list[dict] = []

    for step in range(1, args.steps + 1):
        if cooldown_active(
            conn,
            table=args.log_table,
            chat_id=args.chat_id,
            current_step=step,
            cooldown_steps=args.cooldown_steps,
        ):
            payload = {
                "step": step,
                "reason": "cooldown_blocked",
                "picked": None,
            }
            results.append(payload)
            continue

        fresh = pick_fresh(conn, log_table=args.log_table)
        if fresh is not None:
            reason = "candidate_selected_fresh"
            picked = fresh
        else:
            reuse = pick_reuse(conn)
            if reuse is None:
                reason = "no_active_candidates"
                picked = None
            else:
                reason = "reuse_after_exhaustion"
                picked = reuse

        payload = {
            "step": step,
            "reason": reason,
            "picked": picked,
        }
        results.append(payload)

        if picked is not None:
            log_pick(
                conn,
                table=args.log_table,
                chat_id=args.chat_id,
                item_id=picked["id"],
                step=step,
            )

    summary = analyze(results)
    out = {
        "config": {
            "db": str(args.db),
            "chat_id": args.chat_id,
            "steps": args.steps,
            "cooldown_steps": args.cooldown_steps,
            "log_table": args.log_table,
        },
        "summary": summary,
        "results": results,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
