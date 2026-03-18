from __future__ import annotations

import json
import re
import sqlite3
from collections import Counter
from pathlib import Path


REWRITE_PATTERNS = [
    (r"^Как по-человечески ", "Как обычно "),
    (r"^Как мягко ", "Какими словами лучше "),
    (r"^Как здесь ", "Как обычно здесь "),
    (r"^Как в разговоре ", "Что обычно говорят, когда "),
    (r"^Как сказать ", "Что обычно говорят, когда "),
]


def first_word(text: str) -> str:
    m = re.match(r"[A-Za-zА-Яа-яЁё]+", text.lower())
    return m.group(0) if m else ""


def rewrite(text: str) -> str | None:
    for pattern, repl in REWRITE_PATTERNS:
        if re.match(pattern, text):
            return re.sub(pattern, repl, text)
    return None


def main():
    db = Path("data/lingua_staging.db")
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row

    rows = conn.execute("""
        SELECT id, text, format_type, topic
        FROM community_content_items
        WHERE is_active = 1
    """).fetchall()

    texts = [r["text"] for r in rows]
    first1 = Counter(first_word(t) for t in texts)

    total = len(texts)

    audit = {
        "total": total,
        "first1_distribution": dict(first1),
        "first1_ratio": {
            k: round(v / total, 3)
            for k, v in first1.items()
        }
    }

    suggestions = []

    for r in rows:
        new_text = rewrite(r["text"])
        if new_text and new_text != r["text"]:
            suggestions.append({
                "id": r["id"],
                "old": r["text"],
                "new": new_text,
                "format_type": r["format_type"],
                "topic": r["topic"]
            })

    out_dir = Path("data/community_quality")
    out_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "community_quality_audit_v1.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    (out_dir / "community_quality_rewrite_suggestions_v1.json").write_text(
        json.dumps(suggestions, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print("===== AUDIT =====")
    print(json.dumps(audit, ensure_ascii=False, indent=2))

    print("\n===== SUGGESTIONS (HEAD 10) =====")
    for s in suggestions[:10]:
        print("\n---")
        print("OLD:", s["old"])
        print("NEW:", s["new"])

    print(f"\nTotal suggestions: {len(suggestions)}")


if __name__ == "__main__":
    main()
