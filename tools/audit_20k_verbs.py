#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path
from typing import Any

DB_PATH = Path("data/lingua.db")
OUT_JSON = Path("tmp/20k_verbs_audit.json")
OUT_CSV = Path("tmp/20k_verbs_audit.csv")


def table_exists(cur: sqlite3.Cursor, name: str) -> bool:
    row = cur.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (name,),
    ).fetchone()
    return row is not None


def table_columns(cur: sqlite3.Cursor, name: str) -> list[str]:
    if not table_exists(cur, name):
        return []
    rows = cur.execute(f"PRAGMA table_info({name})").fetchall()
    return [r[1] for r in rows]


def detect_choice_mapping(cur: sqlite3.Cursor) -> dict[str, Any]:
    cols = table_columns(cur, "vocab_choices")
    info: dict[str, Any] = {"table": "vocab_choices", "exists": bool(cols), "columns": cols}
    if not cols:
        return info

    item_id_col = None
    for cand in ("item_id", "vocab_item_id", "question_id"):
        if cand in cols:
            item_id_col = cand
            break

    text_col = None
    for cand in ("choice_text", "text", "answer_text", "label"):
        if cand in cols:
            text_col = cand
            break

    is_correct_col = None
    for cand in ("is_correct", "correct", "is_answer"):
        if cand in cols:
            is_correct_col = cand
            break

    sort_col = None
    for cand in ("position", "sort_order", "idx", "id"):
        if cand in cols:
            sort_col = cand
            break

    info.update(
        {
            "item_id_col": item_id_col,
            "text_col": text_col,
            "is_correct_col": is_correct_col,
            "sort_col": sort_col,
        }
    )
    return info


def detect_validation_mapping(cur: sqlite3.Cursor) -> dict[str, Any]:
    cols = table_columns(cur, "vocab_item_validation")
    info: dict[str, Any] = {"table": "vocab_item_validation", "exists": bool(cols), "columns": cols}
    if not cols:
        return info

    item_id_col = None
    for cand in ("item_id", "vocab_item_id"):
        if cand in cols:
            item_id_col = cand
            break

    flag_cols = [c for c in cols if any(x in c.lower() for x in ("flag", "reason", "status", "debug", "json"))]

    info.update(
        {
            "item_id_col": item_id_col,
            "flag_cols": flag_cols,
        }
    )
    return info


def fetch_choices(cur: sqlite3.Cursor, choice_map: dict[str, Any], item_id: int) -> dict[str, Any]:
    if not choice_map.get("exists"):
        return {"available": False, "choice_count": None, "correct_count": None, "choices": []}

    item_id_col = choice_map.get("item_id_col")
    text_col = choice_map.get("text_col")
    is_correct_col = choice_map.get("is_correct_col")
    sort_col = choice_map.get("sort_col")

    if not item_id_col:
        return {"available": False, "choice_count": None, "correct_count": None, "choices": []}

    select_cols = ["id"]
    if text_col:
        select_cols.append(text_col)
    if is_correct_col:
        select_cols.append(is_correct_col)

    q = f"SELECT {', '.join(select_cols)} FROM vocab_choices WHERE {item_id_col} = ?"
    if sort_col:
        q += f" ORDER BY {sort_col} ASC"
    else:
        q += " ORDER BY id ASC"

    rows = cur.execute(q, (item_id,)).fetchall()
    result_choices = []
    correct_count = 0
    for r in rows:
        d = dict(r)
        txt = d.get(text_col) if text_col else None
        corr = d.get(is_correct_col) if is_correct_col else None
        if corr == 1:
            correct_count += 1
        result_choices.append({"text": txt, "is_correct": corr})

    return {
        "available": True,
        "choice_count": len(rows),
        "correct_count": correct_count if is_correct_col else None,
        "choices": result_choices,
    }


def fetch_validation(cur: sqlite3.Cursor, val_map: dict[str, Any], item_id: int) -> dict[str, Any]:
    if not val_map.get("exists") or not val_map.get("item_id_col"):
        return {"available": False, "rows": []}

    item_id_col = val_map["item_id_col"]
    cols = val_map["columns"]
    q = f"SELECT {', '.join(cols)} FROM vocab_item_validation WHERE {item_id_col} = ? ORDER BY rowid ASC"
    rows = cur.execute(q, (item_id,)).fetchall()
    return {"available": True, "rows": [dict(r) for r in rows]}


def main() -> None:
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    choice_map = detect_choice_mapping(cur)
    val_map = detect_validation_mapping(cur)

    item_rows = cur.execute(
        """
        SELECT id, lemma, correct_answer, freq_rank, is_active, bin_name, topic_tag
        FROM vocab_items
        WHERE pos = 'verb'
          AND freq_rank IS NOT NULL
          AND bin_name = '20K'
        ORDER BY freq_rank DESC, lemma ASC
        """
    ).fetchall()

    report: dict[str, Any] = {
        "db_path": str(DB_PATH),
        "choice_map": choice_map,
        "validation_map": val_map,
        "count": len(item_rows),
        "items": [],
    }

    csv_rows: list[dict[str, Any]] = []

    for row in item_rows:
        item = dict(row)
        item_id = item["id"]

        choices = fetch_choices(cur, choice_map, item_id)
        validation = fetch_validation(cur, val_map, item_id)

        choice_health = "UNKNOWN"
        if choices["available"]:
            if choices["choice_count"] != 6:
                choice_health = "BAD_CHOICE_COUNT"
            elif choices["correct_count"] != 1:
                choice_health = "BAD_CORRECT_COUNT"
            else:
                choice_health = "OK"

        flags_flat: list[str] = []
        for vr in validation["rows"]:
            for k, v in vr.items():
                if v is None:
                    continue
                ks = k.lower()
                if any(x in ks for x in ("flag", "reason", "status")):
                    flags_flat.append(f"{k}={v}")

        item_report = {
            **item,
            "choice_health": choice_health,
            "choice_count": choices["choice_count"],
            "correct_count": choices["correct_count"],
            "choices": choices["choices"],
            "validation_rows": validation["rows"],
            "validation_flags_flat": flags_flat,
        }
        report["items"].append(item_report)

        csv_rows.append(
            {
                "id": item["id"],
                "lemma": item["lemma"],
                "correct_answer": item["correct_answer"],
                "freq_rank": item["freq_rank"],
                "is_active": item["is_active"],
                "choice_health": choice_health,
                "choice_count": choices["choice_count"],
                "correct_count": choices["correct_count"],
                "validation_flags_flat": " | ".join(flags_flat),
            }
        )

    with OUT_JSON.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "id",
                "lemma",
                "correct_answer",
                "freq_rank",
                "is_active",
                "choice_health",
                "choice_count",
                "correct_count",
                "validation_flags_flat",
            ],
        )
        writer.writeheader()
        writer.writerows(csv_rows)

    print("===== AUDIT SUMMARY =====")
    print(json.dumps(
        {
            "count": report["count"],
            "choice_map": choice_map,
            "validation_map": val_map,
            "out_json": str(OUT_JSON),
            "out_csv": str(OUT_CSV),
        },
        ensure_ascii=False,
        indent=2,
    ))
    print("\n===== CSV PREVIEW =====")
    for row in csv_rows:
        print(row)

    conn.close()


if __name__ == "__main__":
    main()
