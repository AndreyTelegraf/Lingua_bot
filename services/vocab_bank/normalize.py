from __future__ import annotations

import json
import re
import sqlite3
import unicodedata
from dataclasses import dataclass


_WS_RE = re.compile(r"\s+")
_EDGE_PUNCT_RE = re.compile(r"^[\s\-\.,;:!?\"'«»„“”()\[\]{}<>/\\|]+|[\s\-\.,;:!?\"'«»„“”()\[\]{}<>/\\|]+$")
_GLOSS_TRASH_RE = re.compile(r"^\s*(to\s+|[0-9]+\.\s*|\[[^\]]*\]\s*|\([^)]+\)\s*)+", re.IGNORECASE)


@dataclass(slots=True)
class NormalizedCandidate:
    source_name: str
    normalized_lemma: str
    lemma_key: str
    pos: str | None
    level: str | None
    freq_rank: int | None
    ru_gloss: str | None
    gloss_key: str | None
    is_eligible: int
    reject_reason: str | None
    payload_json: str


def _collapse_ws(value: str) -> str:
    return _WS_RE.sub(" ", value).strip()


def normalize_lemma(value: str | None) -> str | None:
    if value is None:
        return None
    s = unicodedata.normalize("NFC", value).strip().lower()
    s = _EDGE_PUNCT_RE.sub("", s)
    s = _collapse_ws(s)
    return s or None


def normalize_gloss(value: str | None) -> str | None:
    if value is None:
        return None
    s = unicodedata.normalize("NFC", value).strip()
    s = _GLOSS_TRASH_RE.sub("", s)
    s = _EDGE_PUNCT_RE.sub("", s)
    s = _collapse_ws(s)
    return s or None


def make_lemma_key(normalized_lemma: str | None) -> str | None:
    if normalized_lemma is None:
        return None
    return normalized_lemma


def make_gloss_key(normalized_gloss: str | None) -> str | None:
    if normalized_gloss is None:
        return None
    return normalized_gloss.casefold()


def _parse_freq_rank(raw_freq: str | None) -> int | None:
    if raw_freq is None:
        return None
    s = raw_freq.strip()
    if not s:
        return None
    try:
        return int(float(s))
    except ValueError:
        return None


def build_candidate_from_raw_row(row: sqlite3.Row) -> NormalizedCandidate:
    normalized_lemma = normalize_lemma(row["raw_lemma"])
    normalized_gloss = normalize_gloss(row["raw_gloss_ru"])
    lemma_key = make_lemma_key(normalized_lemma)
    gloss_key = make_gloss_key(normalized_gloss)
    freq_rank = _parse_freq_rank(row["raw_freq"])

    reject_reason = None
    is_eligible = 1

    if not normalized_lemma:
        is_eligible = 0
        reject_reason = "missing_lemma"
    elif not normalized_gloss:
        is_eligible = 0
        reject_reason = "missing_gloss"

    payload = {
        "raw_entry_id": row["id"],
        "source_name": row["source_name"],
        "raw_lemma": row["raw_lemma"],
        "raw_pos": row["raw_pos"],
        "raw_level": row["raw_level"],
        "raw_freq": row["raw_freq"],
        "raw_gloss_ru": row["raw_gloss_ru"],
    }

    return NormalizedCandidate(
        source_name=str(row["source_name"]),
        normalized_lemma=normalized_lemma or "",
        lemma_key=lemma_key or "",
        pos=(str(row["raw_pos"]).strip() if row["raw_pos"] is not None and str(row["raw_pos"]).strip() else None),
        level=(str(row["raw_level"]).strip() if row["raw_level"] is not None and str(row["raw_level"]).strip() else None),
        freq_rank=freq_rank,
        ru_gloss=normalized_gloss,
        gloss_key=gloss_key,
        is_eligible=is_eligible,
        reject_reason=reject_reason,
        payload_json=json.dumps(payload, ensure_ascii=False, sort_keys=True),
    )


def normalize_raw_entries_to_candidates(
    conn: sqlite3.Connection,
    *,
    source_name: str | None = None,
    truncate_source: bool = False,
) -> int:
    conn.row_factory = sqlite3.Row

    sql = """
    SELECT id, source_name, external_key, raw_lemma, raw_pos, raw_level, raw_freq, raw_gloss_ru, payload_json
    FROM vocab_raw_entries
    """
    params: tuple[object, ...] = ()
    if source_name:
        sql += " WHERE source_name = ?"
        params = (source_name,)

    rows = conn.execute(sql, params).fetchall()
    if not rows:
        return 0

    source_names = sorted({str(r["source_name"]) for r in rows})
    if truncate_source:
        conn.executemany(
            "DELETE FROM vocab_lemma_candidates WHERE source_name = ?",
            [(name,) for name in source_names],
        )

    candidates = [build_candidate_from_raw_row(r) for r in rows]

    conn.executemany(
        """
        INSERT INTO vocab_lemma_candidates (
            build_id,
            source_name,
            source_weight,
            merge_group_id,
            normalized_lemma,
            lemma_key,
            pos,
            level,
            freq_rank,
            ru_gloss,
            gloss_key,
            is_eligible,
            reject_reason,
            payload_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                None,
                c.source_name,
                None,
                None,
                c.normalized_lemma,
                c.lemma_key,
                c.pos,
                c.level,
                c.freq_rank,
                c.ru_gloss,
                c.gloss_key,
                c.is_eligible,
                c.reject_reason,
                c.payload_json,
            )
            for c in candidates
        ],
    )
    conn.commit()
    return len(candidates)
