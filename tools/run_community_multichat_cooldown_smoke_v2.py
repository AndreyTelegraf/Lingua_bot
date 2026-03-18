from __future__ import annotations

import argparse
import json
import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path


DEFAULT_CHAT_IDS = [
    -1001690275466,  # chatalgarve
    -1001656765898,  # chatlisboa
    -1001719116315,  # chatporto
    -1001227461571,  # chatleiria
]


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
            delivered_at_tick INTEGER NOT NULL
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
    current_tick: int,
    cooldown_ticks: int,
) -> bool:
    row = conn.execute(
        f"""
        SELECT MAX(delivered_at_tick)
        FROM {table}
        WHERE chat_id = ?
        """,
        (chat_id,),
    ).fetchone()
    last_tick = row[0]
    if last_tick is None:
        return False
    return (current_tick - last_tick) < cooldown_ticks


def pick_fresh_for_chat(
    conn: sqlite3.Connection,
    *,
    log_table: str,
    chat_id: int,
) -> dict | None:
    row = conn.execute(
        f"""
        SELECT id, text, format_type, topic, priority
        FROM community_content_items
        WHERE is_active = 1
          AND id NOT IN (
            SELECT item_id
            FROM {log_table}
            WHERE chat_id = ?
              AND item_id IS NOT NULL
          )
        ORDER BY priority ASC, id ASC
        LIMIT 1
        """,
        (chat_id,),
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
    tick: int,
) -> None:
    conn.execute(
        f"""
        INSERT INTO {table} (chat_id, item_id, delivered_at_tick)
        VALUES (?, ?, ?)
        """,
        (chat_id, item_id, tick),
    )
    conn.commit()


def analyze_chat(results: list[dict]) -> dict:
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
    parser.add_argument("--ticks", type=int, default=40)
    parser.add_argument("--cooldown-ticks", type=int, default=3)
    parser.add_argument("--log-table", default="community_delivery_log_smoke_v2")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--chat-ids", nargs="*", type=int, default=DEFAULT_CHAT_IDS)
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row

    ensure_smoke_log_table(conn, args.log_table)
    reset_smoke_log_table(conn, args.log_table)

    global_results: list[dict] = []
    by_chat: dict[int, list[dict]] = defaultdict(list)

    for tick in range(1, args.ticks + 1):
        for chat_id in args.chat_ids:
            if cooldown_active(
                conn,
                table=args.log_table,
                chat_id=chat_id,
                current_tick=tick,
                cooldown_ticks=args.cooldown_ticks,
            ):
                payload = {
                    "tick": tick,
                    "chat_id": chat_id,
                    "reason": "cooldown_blocked",
                    "picked": None,
                }
                global_results.append(payload)
                by_chat[chat_id].append(payload)
                continue

            fresh = pick_fresh_for_chat(conn, log_table=args.log_table, chat_id=chat_id)
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
                "tick": tick,
                "chat_id": chat_id,
                "reason": reason,
                "picked": picked,
            }
            global_results.append(payload)
            by_chat[chat_id].append(payload)

            if picked is not None:
                log_pick(
                    conn,
                    table=args.log_table,
                    chat_id=chat_id,
                    item_id=picked["id"],
                    tick=tick,
                )

    global_reason_counts = Counter(r["reason"] for r in global_results)
    chat_summaries = {str(chat_id): analyze_chat(rows) for chat_id, rows in by_chat.items()}

    out = {
        "config": {
            "db": str(args.db),
            "ticks": args.ticks,
            "cooldown_ticks": args.cooldown_ticks,
            "log_table": args.log_table,
            "chat_ids": args.chat_ids,
        },
        "global_summary": {
            "reason_counts": dict(global_reason_counts),
            "total_events": len(global_results),
        },
        "chat_summaries": chat_summaries,
        "results_head": global_results[:80],
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
