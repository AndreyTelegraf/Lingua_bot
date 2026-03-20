import csv
import json
import shutil
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path("/home/andrey/Projects/lingua_bot_v2")
DB = ROOT / "data/lingua_staging.db"
OUT_DIR = ROOT / "data/community_authoring/community_cleanup_weak_items_v1"
OUT_DIR.mkdir(parents=True, exist_ok=True)

IMPORTED_ID_GT = 387

HIGH_CONFIDENCE_PATTERNS = [
    "чтобы это звучало естественно и по-живому",
    "чтобы это звучало естественно",
    "чтобы это звучало по-живому",
]

MEDIUM_REVIEW_PATTERNS = [
    "по-человечески",
    "без канцелярита",
    "без кринжа",
    "как здесь обычно скажут",
]

def norm(s: str) -> str:
    return " ".join((s or "").strip().split())

def classify(text: str):
    t = norm(text).lower()
    reasons_safe = []
    reasons_review = []

    for p in HIGH_CONFIDENCE_PATTERNS:
        if p in t:
            reasons_safe.append(f"meta_tail::{p}")

    for p in MEDIUM_REVIEW_PATTERNS:
        if p in t:
            reasons_review.append(f"review_phrase::{p}")

    ln = len(norm(text))
    if ln >= 170:
        reasons_review.append(f"long::{ln}")

    if t.startswith("в какой форме лучше спросить"):
        reasons_review.append("opener_rigid::в какой форме лучше спросить")
    if t.startswith("какими словами лучше сказать"):
        reasons_review.append("opener_rigid::какими словами лучше сказать")
    if t.startswith("что обычно спрашивают здесь"):
        reasons_review.append("opener_rigid::что обычно спрашивают здесь")

    safe = len(reasons_safe) > 0
    review = len(reasons_review) > 0 or safe
    return {
        "safe_reasons": reasons_safe,
        "review_reasons": reasons_review,
        "is_safe_deactivate": safe,
        "is_review_candidate": review,
        "length": ln,
    }

def main():
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup_path = OUT_DIR / f"lingua_staging_before_cleanup_{stamp}.db"
    shutil.copy2(DB, backup_path)

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    rows = [dict(r) for r in conn.execute("""
        select id, topic, format_type, is_active, has_question, text, created_at, updated_at
        from community_content_items
        where id > ?
        order by id
    """, (IMPORTED_ID_GT,))]

    classified = []
    safe_ids = []
    review_rows = []
    reason_counter = Counter()

    for r in rows:
        cls = classify(r["text"] or "")
        item = {
            **r,
            **cls,
        }
        classified.append(item)

        for x in cls["safe_reasons"] + cls["review_reasons"]:
            reason_counter[x] += 1

        if cls["is_safe_deactivate"] and int(r["is_active"]) == 1:
            safe_ids.append(int(r["id"]))

        if cls["is_review_candidate"]:
            review_rows.append(item)

    apply_summary = {
        "imported_rows_scanned": len(rows),
        "safe_deactivate_count": len(safe_ids),
        "review_candidate_count": len(review_rows),
        "backup_path": str(backup_path.relative_to(ROOT)),
        "imported_id_gt": IMPORTED_ID_GT,
        "reason_counts": dict(reason_counter),
    }

    if safe_ids:
        q = ",".join("?" for _ in safe_ids)
        conn.execute(
            f"""
            update community_content_items
            set is_active = 0,
                updated_at = datetime('now')
            where id in ({q})
            """,
            safe_ids,
        )
        conn.commit()

    active_after = conn.execute("""
        select count(*) as c
        from community_content_items
        where is_active = 1
    """).fetchone()["c"]

    imported_active_after = conn.execute("""
        select count(*) as c
        from community_content_items
        where id > ? and is_active = 1
    """, (IMPORTED_ID_GT,)).fetchone()["c"]

    final_summary = {
        **apply_summary,
        "safe_deactivated_ids": safe_ids,
        "active_total_after": active_after,
        "imported_active_after": imported_active_after,
    }

    (OUT_DIR / "summary.json").write_text(
        json.dumps(final_summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (OUT_DIR / "classified_rows.json").write_text(
        json.dumps(classified, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (OUT_DIR / "review_candidates.json").write_text(
        json.dumps(review_rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    with (OUT_DIR / "review_candidates.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "id","topic","format_type","is_active","length",
                "safe_reasons","review_reasons","text"
            ],
        )
        w.writeheader()
        for r in review_rows:
            row = {
                "id": r["id"],
                "topic": r["topic"],
                "format_type": r["format_type"],
                "is_active": r["is_active"],
                "length": r["length"],
                "safe_reasons": " | ".join(r["safe_reasons"]),
                "review_reasons": " | ".join(r["review_reasons"]),
                "text": r["text"],
            }
            w.writerow(row)

    post = {
        "active_by_topic": {
            r["topic"]: r["c"] for r in conn.execute("""
                select topic, count(*) as c
                from community_content_items
                where is_active = 1
                group by topic
                order by topic
            """)
        },
        "active_by_format_type": {
            r["format_type"]: r["c"] for r in conn.execute("""
                select format_type, count(*) as c
                from community_content_items
                where is_active = 1
                group by format_type
                order by format_type
            """)
        },
        "last_imported_rows": [dict(r) for r in conn.execute("""
            select id, topic, format_type, is_active, text
            from community_content_items
            where id > ?
            order by id desc
            limit 20
        """, (IMPORTED_ID_GT,))]
    }
    (OUT_DIR / "post_cleanup_snapshot.json").write_text(
        json.dumps(post, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(final_summary, ensure_ascii=False, indent=2))
    conn.close()

if __name__ == "__main__":
    main()
