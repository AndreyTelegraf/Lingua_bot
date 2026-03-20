import csv
import json
import sqlite3
from collections import Counter
from pathlib import Path

ROOT = Path("/home/andrey/Projects/lingua_bot_v2")
DB = ROOT / "data/lingua_staging.db"
OUT_DIR = ROOT / "data/community_authoring/community_audit_imported_batch_v2"
OUT_DIR.mkdir(parents=True, exist_ok=True)

IMPORTED_ID_GT = 387

OPENERS = [
    "в какой форме лучше спросить",
    "какими словами лучше сказать",
    "как бы вы",
    "что обычно спрашивают здесь",
    "какими словами аккуратно спросили",
]

TAILS = [
    "без канцелярита",
    "без кринжа",
    "как здесь обычно скажут",
    "естественно и по-живому",
    "естественно",
    "по-живому",
]

def norm(s: str) -> str:
    return " ".join((s or "").strip().split())

def classify(text: str):
    t = norm(text)
    low = t.lower()
    reasons = []

    ln = len(t)
    if ln >= 150:
        reasons.append(f"long::{ln}")
    elif ln >= 135:
        reasons.append(f"medium_long::{ln}")

    for opener in OPENERS:
        if low.startswith(opener):
            reasons.append(f"rigid_opener::{opener}")

    for tail in TAILS:
        if tail in low:
            reasons.append(f"tail_phrase::{tail}")

    if "когда" in low and low.count(" и ") >= 2 and ln >= 130:
        reasons.append("compound_heavy")

    if ":" in t and ln >= 110:
        reasons.append("colon_heavy")

    return reasons

def main():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    rows = [dict(r) for r in conn.execute("""
        select id, topic, format_type, is_active, has_question, text
        from community_content_items
        where id > ?
        order by id
    """, (IMPORTED_ID_GT,))]

    flagged = []
    reason_counts = Counter()

    for r in rows:
        reasons = classify(r["text"] or "")
        if reasons:
            item = {
                **r,
                "length": len(norm(r["text"] or "")),
                "reasons": reasons,
            }
            flagged.append(item)
            for x in reasons:
                reason_counts[x] += 1

    summary = {
        "imported_rows_scanned": len(rows),
        "flagged_count": len(flagged),
        "reason_counts": dict(reason_counts),
        "imported_id_gt": IMPORTED_ID_GT,
    }

    (OUT_DIR / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (OUT_DIR / "flagged.json").write_text(
        json.dumps(flagged, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    with (OUT_DIR / "flagged.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "id","topic","format_type","is_active","has_question","length","reasons","text"
            ],
        )
        w.writeheader()
        for r in flagged:
            w.writerow({
                "id": r["id"],
                "topic": r["topic"],
                "format_type": r["format_type"],
                "is_active": r["is_active"],
                "has_question": r["has_question"],
                "length": r["length"],
                "reasons": " | ".join(r["reasons"]),
                "text": r["text"],
            })

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    conn.close()

if __name__ == "__main__":
    main()
