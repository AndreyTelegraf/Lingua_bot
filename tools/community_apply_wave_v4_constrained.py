from __future__ import annotations

import csv
import json
import shutil
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import re

ROOT = Path("/home/andrey/Projects/lingua_bot_v2")
DB_PATH = ROOT / "data/lingua_staging.db"
SRC_TSV = ROOT / "data/community_review/review_pack_v4/community_review_pack_v4.tsv"
OUT_DIR = ROOT / "data/community_apply"
SUMMARY_PATH = OUT_DIR / "community_apply_wave_v4_constrained_summary.json"
BACKUP_DIR = ROOT / "data/community_apply/backups"

TABLE = "community_content_items"

def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

def toks(s: str) -> list[str]:
    return re.findall(r"[^\W_]+", (s or "").lower(), flags=re.UNICODE)

def audit(conn: sqlite3.Connection) -> dict:
    rows = conn.execute("""
        SELECT id, text, format_type, topic
        FROM community_content_items
        WHERE is_active = 1
        ORDER BY id
    """).fetchall()

    first1 = Counter()
    first2 = Counter()
    first3 = Counter()
    topics = Counter()
    formats = Counter()

    for row in rows:
        text = row["text"] or ""
        t = toks(text)
        if len(t) >= 1:
            first1[" ".join(t[:1])] += 1
        if len(t) >= 2:
            first2[" ".join(t[:2])] += 1
        if len(t) >= 3:
            first3[" ".join(t[:3])] += 1
        topics[(row["topic"] or "").strip()] += 1
        formats[(row["format_type"] or "").strip()] += 1

    return {
        "active_count": len(rows),
        "topics": dict(topics),
        "formats": dict(formats),
        "top_first1": first1.most_common(20),
        "top_first2": first2.most_common(20),
        "top_first3": first3.most_common(20),
    }

def load_rows(path: Path):
    rows = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            text = (row.get("text") or "").strip()
            topic = (row.get("topic") or "").strip()
            format_type = (row.get("format_type") or "").strip()
            scenario_id = (row.get("scenario_id") or "").strip()
            if not text or not format_type:
                continue
            rows.append({
                "scenario_id": scenario_id,
                "topic": topic or None,
                "format_type": format_type,
                "text": text,
            })
    return rows

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    if not DB_PATH.exists():
        raise SystemExit(f"DB not found: {DB_PATH}")
    if not SRC_TSV.exists():
        raise SystemExit(f"Source TSV not found: {SRC_TSV}")

    rows = load_rows(SRC_TSV)
    if not rows:
        raise SystemExit("No valid rows found in review_pack_v4.tsv")

    backup_path = BACKUP_DIR / f"lingua_staging_before_community_apply_wave_v4_constrained_{now_utc()}.db"
    shutil.copy2(DB_PATH, backup_path)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    before = audit(conn)
    existing_texts = {
        r["text"].strip()
        for r in conn.execute("SELECT text FROM community_content_items").fetchall()
        if (r["text"] or "").strip()
    }

    inserted = []
    skipped = []

    conn.execute("BEGIN")
    try:
        for row in rows:
            if row["text"] in existing_texts:
                skipped.append({
                    "scenario_id": row["scenario_id"],
                    "reason": "duplicate_text",
                    "text": row["text"],
                })
                continue

            conn.execute("""
                INSERT INTO community_content_items
                (text, format_type, topic, has_question, difficulty, is_active, priority)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                row["text"],
                row["format_type"],
                row["topic"],
                1,
                "light",
                1,
                50,
            ))
            new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            inserted.append({
                "id": int(new_id),
                **row,
            })
            existing_texts.add(row["text"])

        if not inserted:
            raise RuntimeError("Nothing inserted")

        conn.commit()
    except Exception:
        conn.rollback()
        conn.close()
        raise

    after = audit(conn)
    conn.close()

    summary = {
        "status": "ok",
        "db_path": str(DB_PATH),
        "backup_path": str(backup_path),
        "source_tsv": str(SRC_TSV),
        "source_count": len(rows),
        "inserted_count": len(inserted),
        "skipped_count": len(skipped),
        "inserted": inserted,
        "skipped": skipped,
        "before_audit": before,
        "after_audit": after,
    }
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
