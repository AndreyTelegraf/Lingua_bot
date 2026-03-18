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


def load_json(path: Path) -> dict:
    if not path.exists():
        return {"missing": str(path)}
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--runtime-smoke", type=Path, required=True)
    parser.add_argument("--multichat-smoke", type=Path, required=True)
    parser.add_argument("--global-antidup-smoke", type=Path, required=True)
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """
        SELECT id, text, format_type, topic, priority, is_active
        FROM community_content_items
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

    baseline = {
        "active_count": len(rows),
        "topics": dict(topics),
        "formats": dict(formats),
        "first1": dict(first1),
        "first2": dict(first2),
        "first3": dict(first3),
        "length_min": min((len(t) for t in texts), default=0),
        "length_max": max((len(t) for t in texts), default=0),
        "length_avg": round(sum(len(t) for t in texts) / len(texts), 2) if texts else 0,
        "tail_active": [
            {
                "id": row["id"],
                "format_type": row["format_type"],
                "topic": row["topic"],
                "priority": row["priority"],
                "text": row["text"],
            }
            for row in rows[-20:]
        ],
    }

    snapshot = {
        "baseline": baseline,
        "runtime_adjacent_smoke_v1": load_json(args.runtime_smoke),
        "multichat_cooldown_smoke_v2": load_json(args.multichat_smoke),
        "global_antidup_smoke_v3": load_json(args.global_antidup_smoke),
    }

    args.out_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = args.out_dir / "community_baseline_snapshot_v1.json"
    summary_path = args.out_dir / "community_baseline_summary_v1.json"

    snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = {
        "active_count": baseline["active_count"],
        "formats": baseline["formats"],
        "topics": baseline["topics"],
        "top_first1": dict(first1.most_common(8)),
        "top_first2": dict(first2.most_common(10)),
        "top_first3": dict(first3.most_common(12)),
        "runtime_reason_counts": snapshot["runtime_adjacent_smoke_v1"].get("summary", {}).get("reason_counts", {}),
        "multichat_reason_counts": snapshot["multichat_cooldown_smoke_v2"].get("global_summary", {}).get("reason_counts", {}),
        "global_antidup_reason_counts": snapshot["global_antidup_smoke_v3"].get("global_summary", {}).get("reason_counts", {}),
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
