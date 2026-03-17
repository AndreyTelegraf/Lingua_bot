from __future__ import annotations

import os
import sys

if os.environ.get("LINGUABOT_ALLOW_UNSAFE_DIRECT_ACTIVATION") != "1":
    raise SystemExit(
        "Blocked: this legacy script performs direct vocab_items.is_active=1 writes and bypasses the strict activation gate in services/vocab_bank/validate_items.py. "
        "Use the canonical publish path instead. "
        "Override only for forensic/manual recovery with LINGUABOT_ALLOW_UNSAFE_DIRECT_ACTIVATION=1."
    )


import json
import sqlite3
from pathlib import Path
from datetime import datetime, UTC

BASE = Path("/home/andrey/Projects/lingua_bot_v2")
DB = BASE / "data" / "lingua_staging.db"
OUT_DIR = BASE / "artifacts" / f"rebuild_single_2k_adverb_ontem_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"

TARGET_ID = 31
CORRECT = "вчера"
DISTRACTORS = ["поздно", "наконец", "медленно", "редко", "обычно"]

OUT_DIR.mkdir(parents=True, exist_ok=True)

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

backup = OUT_DIR / "lingua_staging_backup.db"
with open(DB, "rb") as src, open(backup, "wb") as dst:
    dst.write(src.read())

item = conn.execute("""
    SELECT id, lemma, pos, bin_name, correct_answer
    FROM vocab_items
    WHERE id = ?
""", (TARGET_ID,)).fetchone()

if item is None:
    raise SystemExit("target item not found")

conn.execute("DELETE FROM vocab_choices WHERE item_id = ?", (TARGET_ID,))

choices = [CORRECT] + DISTRACTORS
for idx, text in enumerate(choices, start=1):
    conn.execute("""
        INSERT INTO vocab_choices (item_id, choice_text, is_correct, position_index)
        VALUES (?, ?, ?, ?)
    """, (TARGET_ID, text, 1 if text == CORRECT else 0, idx))

conn.execute("UPDATE vocab_items SET is_active = 1 WHERE id = ?", (TARGET_ID,))
conn.commit()

post = conn.execute("""
    SELECT choice_text, is_correct, position_index
    FROM vocab_choices
    WHERE item_id = ?
    ORDER BY position_index, id
""", (TARGET_ID,)).fetchall()

summary = {
    "target_id": TARGET_ID,
    "lemma": item["lemma"],
    "pos": item["pos"],
    "bin_name": item["bin_name"],
    "backup": str(backup),
    "choices_after": [
        {
            "position_index": r["position_index"],
            "choice_text": r["choice_text"],
            "is_correct": r["is_correct"],
        }
        for r in post
    ],
    "choice_count": len(post),
    "correct_count": sum(1 for r in post if r["is_correct"] == 1),
    "active_after": conn.execute("SELECT is_active FROM vocab_items WHERE id = ?", (TARGET_ID,)).fetchone()[0],
}

(OUT_DIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False, indent=2))

conn.close()
