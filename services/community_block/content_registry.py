from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Iterable

from services.community_block import repo

_WS_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[\"'“”‘’`´.,!?;:()\[\]{}<>«»…—–-]+")


def normalize_text(text: str) -> str:
    value = str(text or "").strip().lower().replace("ё", "е")
    value = _PUNCT_RE.sub(" ", value)
    value = _WS_RE.sub(" ", value).strip()
    return value


def fingerprint_text(text: str) -> str:
    return hashlib.sha1(normalize_text(text).encode("utf-8")).hexdigest()


def load_existing_fingerprints(conn: sqlite3.Connection) -> dict[str, list[dict[str, Any]]]:
    rows = conn.execute(
        """
        SELECT id, text, format_type, topic, region, is_active, priority
        FROM community_content_items
        ORDER BY id
        """
    ).fetchall()

    out: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        item = dict(row)
        fp = fingerprint_text(item["text"])
        out.setdefault(fp, []).append(item)
    return out


def _candidate_payload(raw: dict[str, Any]) -> dict[str, Any]:
    text = str(raw.get("text", "")).strip()
    if not text:
        raise ValueError("candidate text is empty")

    return {
        "text": text,
        "format_type": str(raw.get("format_type", "nuance")).strip() or "nuance",
        "topic": raw.get("topic"),
        "region": raw.get("region"),
        "has_question": bool(raw.get("has_question", True)),
        "difficulty": str(raw.get("difficulty", "light")).strip() or "light",
        "priority": int(raw.get("priority", 50)),
    }


def import_candidates(
    conn: sqlite3.Connection,
    *,
    items: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    existing = load_existing_fingerprints(conn)
    seen_batch: set[str] = set()

    inserted_ids: list[int] = []
    rejected_existing: list[dict[str, Any]] = []
    rejected_batch: list[dict[str, Any]] = []

    for raw in items:
        payload = _candidate_payload(raw)
        fp = fingerprint_text(payload["text"])

        if fp in seen_batch:
            rejected_batch.append(
                {
                    "text": payload["text"],
                    "fingerprint": fp,
                    "reason": "duplicate_in_batch",
                }
            )
            continue

        if fp in existing:
            rejected_existing.append(
                {
                    "text": payload["text"],
                    "fingerprint": fp,
                    "matches": [row["id"] for row in existing[fp]],
                }
            )
            continue

        new_id = repo.create_content_item(conn, **payload)
        inserted_ids.append(int(new_id))
        seen_batch.add(fp)
        existing.setdefault(
            fp,
            [{"id": new_id, "text": payload["text"]}],
        )

    conn.commit()

    return {
        "inserted_count": len(inserted_ids),
        "inserted_ids": inserted_ids,
        "rejected_existing_count": len(rejected_existing),
        "rejected_existing": rejected_existing,
        "rejected_batch_count": len(rejected_batch),
        "rejected_batch": rejected_batch,
    }


def export_seed_bank(conn: sqlite3.Connection, *, output_path: Path) -> Path:
    rows = conn.execute(
        """
        SELECT id, text, format_type, topic, region, has_question, difficulty, is_active, priority
        FROM community_content_items
        ORDER BY id
        """
    ).fetchall()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        for row in rows:
            item = dict(row)
            item["fingerprint"] = fingerprint_text(str(item["text"]))
            fh.write(json.dumps(item, ensure_ascii=False) + "\n")

    return output_path
