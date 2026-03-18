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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--table", default="community_content_items")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        f"""
        SELECT id, text, format_type, topic, is_active, priority
        FROM {args.table}
        WHERE is_active = 1
        ORDER BY id
        """
    ).fetchall()

    texts = [row["text"] for row in rows]
    topics = Counter((row["topic"] or "") for row in rows)
    formats = Counter(row["format_type"] for row in rows)
    first1 = Counter(first_words(t, 1) for t in texts)
    first2 = Counter(first_words(t, 2) for t in texts)
    first3 = Counter(first_words(t, 3) for t in texts)

    payload = {
        "active_count": len(rows),
        "topics": dict(topics),
        "formats": dict(formats),
        "first1": dict(first1),
        "first2": dict(first2),
        "first3": dict(first3),
        "length_min": min((len(t) for t in texts), default=0),
        "length_max": max((len(t) for t in texts), default=0),
        "length_avg": round(sum(len(t) for t in texts) / len(texts), 2) if texts else 0,
        "last_15_active": [
            {
                "id": row["id"],
                "format_type": row["format_type"],
                "topic": row["topic"],
                "text": row["text"],
            }
            for row in rows[-15:]
        ],
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
