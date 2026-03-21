from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any

from .bank_adapter import map_vocab_rows_to_cat_items
from .item_model import CATItemModel


@dataclass(slots=True)
class CATBankLoadStats:
    total_rows: int
    eligible_rows: int
    skipped_inactive: int
    skipped_missing_question: int
    skipped_missing_answer: int


def _table_exists(conn: sqlite3.Connection, *, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ? LIMIT 1",
        (table,),
    ).fetchone()
    return row is not None


def _has_column(conn: sqlite3.Connection, *, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(str(r[1]) == column for r in rows)


def _clean_str(value: Any) -> str:
    return str(value or "").strip()


def load_vocab_rows_for_cat(
    conn: sqlite3.Connection,
    *,
    active_only: bool = True,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    if not _table_exists(conn, table="vocab_items"):
        return []

    cols = ["id", "lemma", "question_text", "correct_answer"]
    optional_cols = [
        "freq_rank",
        "bin_name",
        "level",
        "topic_tag",
        "pos",
        "is_active",
        "difficulty_b",
        "discrimination_a",
        "guessing_c",
        "upper_d",
        "mode",
        "modality",
    ]
    for c in optional_cols:
        if _has_column(conn, table="vocab_items", column=c):
            cols.append(c)

    where = []
    params: list[Any] = []

    if active_only and _has_column(conn, table="vocab_items", column="is_active"):
        where.append("is_active = 1")

    sql = f"SELECT {', '.join(cols)} FROM vocab_items"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY id ASC"
    if limit is not None:
        sql += " LIMIT ?"
        params.append(int(limit))

    cur = conn.execute(sql, tuple(params))
    names = [d[0] for d in cur.description]
    out: list[dict[str, Any]] = []
    for row in cur.fetchall():
        out.append({name: row[idx] for idx, name in enumerate(names)})
    return out


def summarize_vocab_rows_eligibility(
    rows: list[dict[str, Any]],
    *,
    active_only: bool = True,
) -> CATBankLoadStats:
    total = 0
    eligible = 0
    skipped_inactive = 0
    skipped_missing_question = 0
    skipped_missing_answer = 0

    for row in rows:
        total += 1

        is_active = row.get("is_active", 1)
        active = bool(is_active) if isinstance(is_active, bool) else str(is_active).strip().lower() not in {"0", "false", "no", "off"}
        if active_only and not active:
            skipped_inactive += 1
            continue

        if _clean_str(row.get("question_text")) == "" and _clean_str(row.get("lemma")) == "":
            skipped_missing_question += 1
            continue

        if _clean_str(row.get("correct_answer")) == "":
            skipped_missing_answer += 1
            continue

        eligible += 1

    return CATBankLoadStats(
        total_rows=total,
        eligible_rows=eligible,
        skipped_inactive=skipped_inactive,
        skipped_missing_question=skipped_missing_question,
        skipped_missing_answer=skipped_missing_answer,
    )


def load_cat_item_bank_from_vocab(
    conn: sqlite3.Connection,
    *,
    active_only: bool = True,
    limit: int | None = None,
    default_mode: str = "vocab",
    default_modality: str = "mcq",
) -> list[CATItemModel]:
    rows = load_vocab_rows_for_cat(
        conn,
        active_only=False,
        limit=limit,
    )

    eligible_rows: list[dict[str, Any]] = []
    for row in rows:
        is_active = row.get("is_active", 1)
        active = bool(is_active) if isinstance(is_active, bool) else str(is_active).strip().lower() not in {"0", "false", "no", "off"}
        if active_only and not active:
            continue
        if _clean_str(row.get("question_text")) == "" and _clean_str(row.get("lemma")) == "":
            continue
        if _clean_str(row.get("correct_answer")) == "":
            continue
        eligible_rows.append(row)

    return map_vocab_rows_to_cat_items(
        eligible_rows,
        default_mode=default_mode,
        default_modality=default_modality,
        active_only=False,
    )
