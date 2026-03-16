#!/usr/bin/env python3
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

STAGING_DB = Path("data/lingua_staging.db")
PROD_DB = Path("data/lingua.db")


def classify_text(s: str | None) -> str:
    s = (s or "").strip()
    if not s:
        return "EMPTY"
    has_cyr = any("А" <= ch <= "я" or ch in "Ёё" for ch in s)
    has_lat = any(
        ("A" <= ch <= "Z") or ("a" <= ch <= "z") or ch in "ÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖØÙÚÛÜÝÞßàáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿ"
        for ch in s
    )
    if has_cyr and has_lat:
        return "MIXED"
    if has_cyr:
        return "CYR"
    if has_lat:
        return "LAT"
    return "OTHER"


def build_prod_lookup(prod_cur: sqlite3.Cursor) -> dict[str, list[dict]]:
    rows = prod_cur.execute(
        """
        SELECT lemma, correct_answer, pos, bin_name, freq_rank, is_active
        FROM vocab_items
        ORDER BY lemma, is_active DESC, freq_rank ASC
        """
    ).fetchall()
    out: dict[str, list[dict]] = {}
    for lemma, correct_answer, pos, bin_name, freq_rank, is_active in rows:
        out.setdefault(lemma, []).append(
            {
                "correct_answer": correct_answer,
                "pos": pos,
                "bin_name": bin_name,
                "freq_rank": freq_rank,
                "is_active": is_active,
            }
        )
    return out


def main() -> None:
    staging = sqlite3.connect(STAGING_DB)
    prod = sqlite3.connect(PROD_DB)

    staging.row_factory = sqlite3.Row
    prod.row_factory = sqlite3.Row

    scur = staging.cursor()
    pcur = prod.cursor()

    prod_lookup = build_prod_lookup(pcur)

    rows = scur.execute(
        """
        SELECT
          vi.id AS item_id,
          vi.lemma,
          vi.pos,
          vi.bin_name,
          vi.freq_rank,
          vi.correct_answer,
          vc.id AS choice_id,
          vc.choice_text,
          vc.position_index
        FROM vocab_items vi
        JOIN vocab_choices vc ON vc.item_id = vi.id
        WHERE vi.is_active = 1
          AND vc.is_correct = 0
        ORDER BY vi.id, vc.position_index, vc.id
        """
    ).fetchall()

    bad = []
    for r in rows:
        correct_answer = r["correct_answer"]
        choice_text = r["choice_text"]
        if classify_text(correct_answer) == "CYR" and classify_text(choice_text) in {"LAT", "MIXED"}:
            bad.append(
                {
                    "item_id": r["item_id"],
                    "lemma": r["lemma"],
                    "pos": r["pos"],
                    "bin_name": r["bin_name"],
                    "freq_rank": r["freq_rank"],
                    "correct_answer": correct_answer,
                    "choice_id": r["choice_id"],
                    "choice_text": choice_text,
                    "position_index": r["position_index"],
                    "prod_lookup": prod_lookup.get(choice_text, []),
                }
            )

    print("===== REMAINING BAD STAGING DISTRACTORS =====")
    print(json.dumps({"count": len(bad)}, ensure_ascii=False, indent=2))
    for row in bad:
        print(json.dumps(row, ensure_ascii=False))

    staging.close()
    prod.close()


if __name__ == "__main__":
    main()
