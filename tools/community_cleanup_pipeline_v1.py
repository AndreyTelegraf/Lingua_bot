#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

ROOT = Path("/home/andrey/Projects/lingua_bot_v2")
DEFAULT_DB = ROOT / "data/lingua_staging.db"
OUT_BASE = ROOT / "data/community_quality"
BACKUP_BASE = OUT_BASE / "backups"
TABLE = "community_content_items"

OPENERS = [
    r"^Как мягко сказать\b",
    r"^Чем люди обычно заменяют\b",
    r"^Что обычно спрашивают(?: здесь)?\b",
    r"^В какой форме лучше спросить\b",
    r"^О ч[её]м обычно уточняют\b",
    r"^Какой оборот здесь\b",
    r"^Как здесь правильно\b",
    r"^Какая фраза здесь\b",
    r"^Как в разговоре обычно скажут\b",
    r"^Какими словами лучше\b",
    r"^Какими словами аккуратно\b",
]
OPENERS_RE = [re.compile(p, re.IGNORECASE) for p in OPENERS]

FILLER_PATTERNS = [
    r"\bчтобы это звучало\b.*$",
    r"\bесли хочется сказать это\b.*$",
    r"\bесли нужен\b.*$",
    r"\bбез канцелярита\b.*$",
    r"\bбез кринжа\b.*$",
    r"\bбез тормозов\b.*$",
    r"\bпо-человечески\b.*$",
]

THEME_RULES: list[tuple[str, list[str]]] = [
    ("cheaper_analog", [r"дешев", r"аналог"]),
    ("copy_original", [r"копи", r"оригинал"]),
    ("courier_redelivery", [r"курьер", r"перенести доставк"]),
    ("next_step_unclear", [r"следующ", r"шаг", r"прямо сейчас"]),
    ("return_exchange", [r"вернут", r"обменят"]),
    ("split_bill", [r"разделит", r"сч[её]т"]),
    ("wifi_password", [r"парол", r"wi[\- ]?fi"]),
]

def load_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        f"""
        SELECT id, topic, format_type, created_at, text
        FROM {TABLE}
        WHERE is_active = 1
        ORDER BY id
        """
    ).fetchall()
    return [dict(r) for r in rows]

def normalize_spaces(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()

def strip_openers(text: str) -> tuple[str | None, str]:
    s = normalize_spaces(text)
    for rx in OPENERS_RE:
        m = rx.match(s)
        if m:
            tail = s[m.end():].lstrip(" ,—:-")
            return rx.pattern, tail
    return None, s

def normalize_tail(text: str) -> tuple[str | None, str]:
    opener, tail = strip_openers(text)
    s = tail.lower().replace("ё", "е")
    s = re.sub(r"[«»\"“”„]", "", s)
    s = s.replace("wi-fi", "wifi").replace("wi fi", "wifi")
    s = re.sub(r"[?!.:,;()]", " ", s)
    for pat in FILLER_PATTERNS:
        s = re.sub(pat, "", s, flags=re.IGNORECASE)
    s = re.sub(r"\bздесь\b", " ", s)
    s = re.sub(r"\bобычно\b", " ", s)
    s = re.sub(r"\bскажут\b", " ", s)
    s = re.sub(r"\bзвучит\b", " ", s)
    s = re.sub(r"\bестественно\b", " ", s)
    s = re.sub(r"\bживо\b", " ", s)
    s = normalize_spaces(s)
    return opener, s

def detect_theme(text: str) -> str | None:
    s = text.lower().replace("ё", "е")
    for theme, needles in THEME_RULES:
        if all(re.search(n, s) for n in needles):
            return theme
    return None

def ts() -> str:
    return datetime.now(UTC).strftime("%Y%m%d_%H%M%S")

def latest_by_keep_policy(items: list[dict[str, Any]]) -> dict[str, Any]:
    return sorted(items, key=lambda r: (r.get("created_at") or "", r["id"]))[-1]

def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "active_count": len(rows),
        "topics": dict(Counter(r["topic"] for r in rows)),
        "formats": dict(Counter(r["format_type"] for r in rows)),
        "head_ids": [r["id"] for r in rows[:20]],
    }

def write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--yes", action="store_true")
    args = ap.parse_args()

    db = Path(args.db)
    if not db.exists():
        raise SystemExit(f"DB not found: {db}")

    run_dir = OUT_BASE / f"community_cleanup_pipeline_v1_{ts()}"
    run_dir.mkdir(parents=True, exist_ok=True)
    BACKUP_BASE.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db)
    rows = load_rows(conn)
    before = summarize(rows)

    for r in rows:
        opener, norm_tail = normalize_tail(r["text"])
        r["normalized_tail"] = norm_tail
        r["opener"] = opener
        r["theme"] = detect_theme(r["text"])

    dup_buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        if r["normalized_tail"]:
            dup_buckets[r["normalized_tail"]].append(r)
    dup_buckets = {k: v for k, v in dup_buckets.items() if len(v) >= 2}

    theme_buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        if r["theme"]:
            theme_buckets[r["theme"]].append(r)
    theme_buckets = {k: v for k, v in theme_buckets.items() if len(v) >= 2}

    target_ids: set[int] = set()
    decisions: list[dict[str, Any]] = []

    for key, items in sorted(dup_buckets.items()):
        keeper = latest_by_keep_policy(items)
        losers = [r for r in items if r["id"] != keeper["id"]]
        for r in losers:
            target_ids.add(r["id"])
        decisions.append({
            "bucket_type": "duplicate_family",
            "bucket_key": key,
            "keep_id": keeper["id"],
            "drop_ids": [r["id"] for r in losers],
            "count": len(items),
        })

    for key, items in sorted(theme_buckets.items()):
        remaining = [r for r in items if r["id"] not in target_ids]
        if len(remaining) <= 1:
            continue
        keeper = latest_by_keep_policy(remaining)
        losers = [r for r in remaining if r["id"] != keeper["id"]]
        for r in losers:
            target_ids.add(r["id"])
        decisions.append({
            "bucket_type": "theme_group",
            "bucket_key": key,
            "keep_id": keeper["id"],
            "drop_ids": [r["id"] for r in losers],
            "count": len(remaining),
        })

    target_rows = [r for r in rows if r["id"] in target_ids]
    preview = {
        "db": str(db),
        "run_dir": str(run_dir),
        "mode": "apply" if args.apply else "dry_run",
        "before": before,
        "duplicate_family_count": len(dup_buckets),
        "theme_group_count": len(theme_buckets),
        "candidate_count": len(target_ids),
        "candidate_ids": sorted(target_ids),
        "candidate_topics": dict(Counter(r["topic"] for r in target_rows)),
        "candidate_formats": dict(Counter(r["format_type"] for r in target_rows)),
        "decisions": decisions,
    }

    write_json(run_dir / "preview.json", preview)
    write_json(run_dir / "decisions.json", decisions)
    (run_dir / "candidate_rows.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in target_rows),
        encoding="utf-8",
    )

    if not args.apply:
        write_json(run_dir / "summary.json", preview)
        print(json.dumps(preview, ensure_ascii=False, indent=2))
        conn.close()
        return 0

    if not args.yes:
        raise SystemExit("--apply requires --yes")

    backup_path = BACKUP_BASE / f"{db.stem}_before_community_cleanup_pipeline_v1_{ts()}.db"
    shutil.copy2(db, backup_path)

    if target_ids:
        qmarks = ",".join("?" for _ in target_ids)
        conn.execute(
            f"UPDATE {TABLE} SET is_active = 0 WHERE id IN ({qmarks})",
            tuple(sorted(target_ids)),
        )
        conn.commit()

    after_rows = load_rows(conn)
    after = summarize(after_rows)
    still_active = [
        r["id"]
        for r in conn.execute(
            f"SELECT id FROM {TABLE} WHERE is_active = 1 AND id IN ({','.join('?' for _ in target_ids)})",
            tuple(sorted(target_ids)) if target_ids else tuple(),
        ).fetchall()
    ] if target_ids else []

    result = {
        **preview,
        "backup_path": str(backup_path),
        "after": after,
        "deactivated_count": len(target_ids),
        "target_ids_still_active": still_active,
        "status": "green" if not still_active else "red",
    }
    write_json(run_dir / "summary.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    conn.close()
    return 0 if not still_active else 1

if __name__ == "__main__":
    raise SystemExit(main())
