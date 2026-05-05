#!/usr/bin/env python3
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

from services.vocab4.certification import (
    load_pending_authoring_items,
    promote_authoring_item,
    reject_authoring_item,
)

DB_PATH = Path("data/lingua_staging.db")


def format_item(item: dict) -> str:
    payload = json.loads(item["payload_json"])
    choices: list[str] = payload["choices"]  # index 0 is always correct
    lines = [
        f"[ID: {item['id']}]",
        f"lemma: {item['lemma']}",
        f"pos: {item['pos']} | bin: {item['bin_name']}",
        f"prompt: {item['prompt']}",
        "choices:",
    ]
    for i, choice in enumerate(choices):
        marker = "   (correct)" if i == 0 else ""
        lines.append(f"  {i}. {choice}{marker}")
    lines.append(f"source: {item['source_name']}")
    return "\n".join(lines)


def handle_action(
    conn: sqlite3.Connection,
    item: dict,
    action: str,
    input_fn=input,
) -> str:
    if action == "a":
        item_id = promote_authoring_item(conn, item["id"])
        print(f"PROMOTED → item_id={item_id}")
        return "promoted"
    if action == "r":
        reason = input_fn("reason > ").strip()
        reject_authoring_item(conn, item["id"], reason)
        print("REJECTED")
        return "rejected"
    if action == "s":
        return "skip"
    if action == "q":
        return "quit"
    return "invalid"


def review_loop(conn: sqlite3.Connection, input_fn=input) -> None:
    items = load_pending_authoring_items(conn)
    if not items:
        print("No pending items.")
        return
    for item in items:
        print(format_item(item))
        result = "invalid"
        while result == "invalid":
            action = input_fn("(a)ccept / (r)eject / (s)kip / (q)uit > ").strip().lower()
            result = handle_action(conn, item, action, input_fn)
        if result == "quit":
            break


def main() -> None:
    if not DB_PATH.exists():
        print(f"ERROR: database not found at {DB_PATH}", file=sys.stderr)
        sys.exit(1)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        review_loop(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
