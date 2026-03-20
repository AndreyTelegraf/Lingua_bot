from __future__ import annotations

import json
import re
import sqlite3
from services.vocab_bank.build_layer_db import ensure_build_db_attached, resolve_build_table
from dataclasses import dataclass


_ALLOWED_POS = {"noun", "verb", "adjective", "adverb"}
_GLOSS_SPLIT_RE = re.compile(r"[,;/]")
_ILLEGAL_LEMMA_RE = re.compile(r"[0-9]")

HARD_LEMMA_BLOCKLIST = {
    "deus",
    "jesus",
    "cristo",
    "maria",
    "lisboa",
    "porto",
    "brasil",
    "angola",
    "mozambique",
}

HARD_GLOSS_BLOCKLIST = {
    "бог",
    "иисус",
    "христос",
    "мария",
    "лиссабон",
    "порту",
}

HARD_SUBSTRING_BLOCKLIST = {
    "igrej",
    "santo",
    "santa",
    "padre",
    "bispo",
    "freira",
    "mosteiro",
    "catedral",
    "paróquia",
    "paroquia",
    "oração",
    "oracao",
    "diocese",
    "evangelho",
    "apóstolo",
    "apostolo",
    "liturgia",
    "sacramento",
    "pecado",
    "milagre",
    "relíquia",
    "reliquia",
    "arcaic",
    "medieval",
}

BRAZILIANISM_HINTS = {
    "ônibus",
    "onibus",
    "trem",
    "celular",
    "banheiro",
    "xerox",
    "açougue",
    "acougue",
    "propina",
}

AFRICANISM_HINTS = {
    "machimbombo",
    "candonga",
    "dumba nengue",
    "cota",
}

@dataclass(slots=True)
class MergedCandidate:
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
    merge_group_id: str
    payload_json: str


def gloss_quality_score(gloss: str | None) -> tuple[int, int, int]:
    if not gloss:
        return (-999999, -999999, -999999)

    text = gloss.strip()
    words = [w for w in text.split() if w]
    word_count = len(words)

    score = 0

    if 1 <= word_count <= 3:
        score += 30
    elif 4 <= word_count <= 7:
        score += 10
    else:
        score -= 20

    if "(" in text or ")" in text:
        score -= 10
    if "[" in text or "]" in text:
        score -= 10
    if "/" in text or ";" in text:
        score -= 8
    if "," in text:
        score -= 6

    split_parts = [p.strip() for p in _GLOSS_SPLIT_RE.split(text) if p.strip()]
    score -= max(0, len(split_parts) - 1) * 4

    return (score, -word_count, -len(text))


def candidate_sort_key(row: sqlite3.Row) -> tuple[object, ...]:
    gloss = row["ru_gloss"]
    freq_rank = row["freq_rank"]
    freq_sort = int(freq_rank) if freq_rank is not None else 999999999
    return (
        gloss_quality_score(str(gloss) if gloss is not None else None),
        -1 if row["level"] is not None else 0,
        -1 if row["source_name"] is not None else 0,
        -freq_sort,
        -int(row["id"]),
    )


def _contains_any(text: str, needles: set[str]) -> bool:
    return any(n in text for n in needles)


def evaluate_candidate_eligibility(row: sqlite3.Row) -> tuple[int, str | None]:
    lemma = str(row["normalized_lemma"]).strip() if row["normalized_lemma"] is not None else ""
    pos = str(row["pos"]).strip() if row["pos"] is not None else ""
    gloss = str(row["ru_gloss"]).strip() if row["ru_gloss"] is not None else ""

    lemma_cf = lemma.casefold()
    gloss_cf = gloss.casefold()

    if not lemma:
        return 0, "missing_lemma"
    if not gloss:
        return 0, "missing_gloss"
    if not pos:
        return 0, "missing_pos"
    if pos not in _ALLOWED_POS:
        return 0, "unsupported_pos"
    if len(lemma) < 2:
        return 0, "lemma_too_short"
    if _ILLEGAL_LEMMA_RE.search(lemma):
        return 0, "illegal_lemma_shape"

    if lemma_cf in HARD_LEMMA_BLOCKLIST or gloss_cf in HARD_GLOSS_BLOCKLIST:
        return 0, "blocked_proper_or_religious_term"

    if _contains_any(lemma_cf, HARD_SUBSTRING_BLOCKLIST):
        return 0, "blocked_religious_or_archaic_term"

    if _contains_any(lemma_cf, BRAZILIANISM_HINTS):
        return 0, "blocked_brazilianism"

    if _contains_any(lemma_cf, AFRICANISM_HINTS):
        return 0, "blocked_africanism"

    return 1, None


def merge_candidates_for_source(
    conn: sqlite3.Connection,
    *,
    source_name: str | None = None,
) -> int:
    conn.row_factory = sqlite3.Row

    lemma_candidates_table = resolve_build_table(conn, "vocab_lemma_candidates")

    sql = f"""
    SELECT
        id,
        source_name,
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
    FROM {lemma_candidates_table}
    """
    params: tuple[object, ...] = ()
    if source_name:
        sql += " WHERE source_name = ?"
        params = (source_name,)

    rows = conn.execute(sql, params).fetchall()
    if not rows:
        return 0

    groups: dict[tuple[str, str], list[sqlite3.Row]] = {}
    for row in rows:
        key = (
            str(row["lemma_key"] or "").strip(),
            str(row["pos"] or "").strip(),
        )
        groups.setdefault(key, []).append(row)

    affected_ids: list[int] = []

    for (lemma_key, pos), group_rows in groups.items():
        group_rows = sorted(group_rows, key=candidate_sort_key, reverse=True)
        winner = group_rows[0]
        merge_group_id = f"{lemma_key}::{pos}" if lemma_key and pos else f"group::{winner['id']}"

        winner_eligible, winner_reason = evaluate_candidate_eligibility(winner)
        winner_payload = json.dumps(
            {
                "merged_from_ids": [int(r["id"]) for r in group_rows],
                "winner_id": int(winner["id"]),
                "merge_group_id": merge_group_id,
                "policy": "best_gloss_by_score_then_freq",
            },
            ensure_ascii=False,
            sort_keys=True,
        )

        conn.execute(
            f"""
            UPDATE {lemma_candidates_table}
            SET
                merge_group_id = ?,
                normalized_lemma = ?,
                lemma_key = ?,
                pos = ?,
                level = ?,
                freq_rank = ?,
                ru_gloss = ?,
                gloss_key = ?,
                is_eligible = ?,
                reject_reason = ?,
                payload_json = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                merge_group_id,
                winner["normalized_lemma"],
                winner["lemma_key"],
                winner["pos"],
                winner["level"],
                winner["freq_rank"],
                winner["ru_gloss"],
                winner["gloss_key"],
                winner_eligible,
                winner_reason,
                winner_payload,
                int(winner["id"]),
            ),
        )
        affected_ids.append(int(winner["id"]))

        for loser in group_rows[1:]:
            loser_payload = json.dumps(
                {
                    "merged_from_ids": [int(r["id"]) for r in group_rows],
                    "winner_id": int(winner["id"]),
                    "merge_group_id": merge_group_id,
                    "policy": "duplicate_loser",
                },
                ensure_ascii=False,
                sort_keys=True,
            )
            conn.execute(
                f"""
                UPDATE {lemma_candidates_table}
                SET
                    merge_group_id = ?,
                    is_eligible = 0,
                    reject_reason = ?,
                    payload_json = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    merge_group_id,
                    "duplicate_lemma_pos",
                    loser_payload,
                    int(loser["id"]),
                ),
            )
            affected_ids.append(int(loser["id"]))

    conn.commit()
    return len(affected_ids)
