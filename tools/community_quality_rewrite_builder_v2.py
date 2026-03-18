from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path


TARGET_PATTERNS = [
    "как сказать ",
    "как здесь правильно спросить, если ",
    "как в разговоре обычно скажут, если ",
    "как по-человечески ",
    "как мягко ",
]

PREFIX_RULES = [
    (
        re.compile(r"^Как сказать (?P<context>.+?), что (?P<body>.+?)\?$", re.IGNORECASE),
        lambda m: f"Что обычно говорят {m.group('context')}, когда {m.group('body')}?"
    ),
    (
        re.compile(r"^Как здесь правильно спросить, если (?P<body>.+?)\?$", re.IGNORECASE),
        lambda m: f"Что обычно спрашивают здесь, когда {m.group('body')}?"
    ),
    (
        re.compile(r"^Как в разговоре обычно скажут, если (?P<body>.+?)\?$", re.IGNORECASE),
        lambda m: f"Что обычно говорят в такой ситуации, когда {m.group('body')}?"
    ),
    (
        re.compile(r"^Как по-человечески (?P<body>.+?)\?$", re.IGNORECASE),
        lambda m: f"Что обычно говорят, когда нужно {m.group('body')}?"
    ),
    (
        re.compile(r"^Как мягко (?P<body>.+?)\?$", re.IGNORECASE),
        lambda m: f"Какими словами лучше {m.group('body')}?"
    ),
]


def normalize(text: str) -> str:
    text = re.sub(r"\s+", " ", text.strip())
    text = re.sub(r"\s+([,?.!])", r"\1", text)
    text = text.replace(" ,", ",")
    text = text.replace("..", ".")
    return text.strip()


def sounds_broken(text: str) -> bool:
    low = text.lower()
    bad_fragments = [
        "когда обычно скажут",
        "обычно здесь правильно",
        "когда в аптеке, что",
        "что обычно говорят, когда нужно что обычно",
        "спрашивают здесь, когда если ",
    ]
    if any(x in low for x in bad_fragments):
        return True
    if "??" in text:
        return True
    return False


def targeted_rewrite(text: str) -> str | None:
    for rx, builder in PREFIX_RULES:
        m = rx.match(text)
        if not m:
            continue
        new_text = normalize(builder(m))
        if new_text == text:
            return None
        if sounds_broken(new_text):
            return None
        return new_text
    return None


def first_word(text: str) -> str:
    m = re.match(r"[A-Za-zА-Яа-яЁё]+", text.lower())
    return m.group(0) if m else ""


def should_consider(text: str) -> bool:
    low = text.lower()
    return any(low.startswith(p) for p in TARGET_PATTERNS)


def main() -> None:
    db = Path("data/lingua_staging.db")
    out_dir = Path("data/community_quality")
    out_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row

    rows = conn.execute("""
        SELECT id, text, format_type, topic
        FROM community_content_items
        WHERE is_active = 1
        ORDER BY id
    """).fetchall()

    candidates = []
    rejected = []

    for r in rows:
        text = r["text"]
        if not should_consider(text):
            continue

        rewritten = targeted_rewrite(text)
        payload = {
            "id": r["id"],
            "old": text,
            "format_type": r["format_type"],
            "topic": r["topic"],
        }

        if rewritten is None:
            payload["reason"] = "no_safe_rewrite"
            rejected.append(payload)
            continue

        payload["new"] = rewritten
        payload["old_first1"] = first_word(text)
        payload["new_first1"] = first_word(rewritten)
        candidates.append(payload)

    summary = {
        "considered_count": len(candidates) + len(rejected),
        "safe_candidate_count": len(candidates),
        "rejected_count": len(rejected),
        "candidate_head": candidates[:10],
        "rejected_head": rejected[:10],
    }

    (out_dir / "community_quality_rewrite_candidates_v2.json").write_text(
        json.dumps(candidates, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out_dir / "community_quality_rewrite_rejected_v2.json").write_text(
        json.dumps(rejected, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out_dir / "community_quality_rewrite_summary_v2.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("===== SUMMARY =====")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    print("\n===== SAFE CANDIDATES HEAD =====")
    for item in candidates[:10]:
        print("\n---")
        print("ID:", item["id"])
        print("OLD:", item["old"])
        print("NEW:", item["new"])

    print("\n===== REJECTED HEAD =====")
    for item in rejected[:10]:
        print("\n---")
        print("ID:", item["id"])
        print("REASON:", item["reason"])
        print("OLD:", item["old"])


if __name__ == "__main__":
    main()
