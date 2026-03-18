from __future__ import annotations

import argparse
import json
import re
import shutil
import sqlite3
from pathlib import Path

PATTERNS = [
    r"^Как бы вы\b",
    r"^Чем в живой\b",
    r"^Как в живой\b",
    r"^Как по-португальски\b",
]


def backup_db(db_path: Path, backup_path: Path) -> None:
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(db_path, backup_path)


def compile_patterns() -> list[re.Pattern[str]]:
    return [re.compile(p, flags=re.IGNORECASE) for p in PATTERNS]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--table", default="community_content_items")
    parser.add_argument("--backup-db", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    patterns = compile_patterns()

    rows = conn.execute(
        f"""
        SELECT id, text, format_type, topic, is_active
        FROM {args.table}
        WHERE is_active = 1
        ORDER BY id
        """
    ).fetchall()

    candidates = []
    for row in rows:
        text = row["text"] or ""
        matched = None
        for pat in patterns:
            if pat.search(text):
                matched = pat.pattern
                break
        if matched:
            candidates.append(
                {
                    "id": row["id"],
                    "text": text,
                    "format_type": row["format_type"],
                    "topic": row["topic"],
                    "matched_pattern": matched,
                }
            )

    deactivated_count = 0

    if args.apply and candidates:
        backup_db(args.db, args.backup_db)
        ids = [c["id"] for c in candidates]
        qmarks = ",".join("?" for _ in ids)
        conn.execute(
            f"""
            UPDATE {args.table}
            SET is_active = 0,
                updated_at = CURRENT_TIMESTAMP
            WHERE id IN ({qmarks})
            """,
            ids,
        )
        conn.commit()
        deactivated_count = len(ids)

    payload = {
        "db": str(args.db),
        "table": args.table,
        "apply": args.apply,
        "pattern_count": len(patterns),
        "candidate_count": len(candidates),
        "deactivated_count": deactivated_count,
        "backup_db": str(args.backup_db) if args.apply and candidates else None,
        "candidates_head": candidates[:25],
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
