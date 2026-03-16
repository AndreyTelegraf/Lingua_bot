#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import re
import sqlite3
from pathlib import Path

DB_PATH = Path("data/lingua.db")
OUT_JSON = Path("tmp/mixed_choice_layer_audit.json")
OUT_CSV = Path("tmp/mixed_choice_layer_audit.csv")

CYR_RE = re.compile(r"[А-Яа-яЁё]")
LAT_RE = re.compile(r"[A-Za-zÀ-ÿ]")

def has_cyr(s: str | None) -> bool:
    return bool(s and CYR_RE.search(s))

def has_lat(s: str | None) -> bool:
    return bool(s and LAT_RE.search(s))

def classify_text(s: str | None) -> str:
    s = (s or "").strip()
    if not s:
        return "EMPTY"
    cyr = has_cyr(s)
    lat = has_lat(s)
    if cyr and lat:
        return "MIXED"
    if cyr:
        return "CYR"
    if lat:
        return "LAT"
    return "OTHER"

def main() -> None:
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    lemma_set = {
        row["lemma"]
        for row in cur.execute("SELECT lemma FROM vocab_items").fetchall()
        if row["lemma"]
    }

    rows = cur.execute(
        """
        SELECT
          vi.id,
          vi.lemma,
          vi.pos,
          vi.bin_name,
          vi.freq_rank,
          vi.correct_answer,
          vi.is_active,
          vc.choice_text,
          vc.is_correct,
          vc.position_index
        FROM vocab_items vi
        JOIN vocab_choices vc ON vc.item_id = vi.id
        WHERE vi.is_active = 1
        ORDER BY vi.id, vc.position_index, vc.id
        """
    ).fetchall()

    by_item: dict[int, dict] = {}
    for r in rows:
        item_id = r["id"]
        item = by_item.setdefault(
            item_id,
            {
                "id": r["id"],
                "lemma": r["lemma"],
                "pos": r["pos"],
                "bin_name": r["bin_name"],
                "freq_rank": r["freq_rank"],
                "correct_answer": r["correct_answer"],
                "correct_answer_class": classify_text(r["correct_answer"]),
                "choices": [],
            },
        )
        txt = r["choice_text"]
        item["choices"].append(
            {
                "choice_text": txt,
                "choice_class": classify_text(txt),
                "is_correct": r["is_correct"],
                "position_index": r["position_index"],
                "equals_some_lemma": txt in lemma_set if txt else False,
            }
        )

    suspicious_items = []
    stats = {
        "active_items_seen": len(by_item),
        "items_with_any_issue": 0,
        "items_with_lat_distractor_when_answer_cyr": 0,
        "items_with_distractor_equal_to_some_lemma": 0,
        "total_bad_distractors": 0,
    }

    csv_rows = []

    for item in by_item.values():
        answer_class = item["correct_answer_class"]
        bad_reasons = []
        bad_distractors = []

        for ch in item["choices"]:
            if ch["is_correct"] == 1:
                continue

            reasons = []
            if answer_class == "CYR" and ch["choice_class"] in {"LAT", "MIXED"}:
                reasons.append("LAT_DISTRACTOR_WHEN_ANSWER_CYR")
            if ch["equals_some_lemma"]:
                reasons.append("DISTRACTOR_EQUALS_LEMMA")

            if reasons:
                bad_distractors.append(
                    {
                        "choice_text": ch["choice_text"],
                        "choice_class": ch["choice_class"],
                        "reasons": reasons,
                    }
                )
                bad_reasons.extend(reasons)
                stats["total_bad_distractors"] += 1

        if bad_distractors:
            uniq = sorted(set(bad_reasons))
            if "LAT_DISTRACTOR_WHEN_ANSWER_CYR" in uniq:
                stats["items_with_lat_distractor_when_answer_cyr"] += 1
            if "DISTRACTOR_EQUALS_LEMMA" in uniq:
                stats["items_with_distractor_equal_to_some_lemma"] += 1
            stats["items_with_any_issue"] += 1

            suspicious_items.append(
                {
                    "id": item["id"],
                    "lemma": item["lemma"],
                    "pos": item["pos"],
                    "bin_name": item["bin_name"],
                    "freq_rank": item["freq_rank"],
                    "correct_answer": item["correct_answer"],
                    "correct_answer_class": answer_class,
                    "issue_codes": uniq,
                    "bad_distractors": bad_distractors,
                }
            )

            csv_rows.append(
                {
                    "id": item["id"],
                    "lemma": item["lemma"],
                    "pos": item["pos"],
                    "bin_name": item["bin_name"],
                    "freq_rank": item["freq_rank"],
                    "correct_answer": item["correct_answer"],
                    "issue_codes": "|".join(uniq),
                    "bad_distractors": " || ".join(
                        f"{d['choice_text']} [{','.join(d['reasons'])}]"
                        for d in bad_distractors
                    ),
                }
            )

    report = {
        "stats": stats,
        "suspicious_items": suspicious_items,
    }

    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "id",
                "lemma",
                "pos",
                "bin_name",
                "freq_rank",
                "correct_answer",
                "issue_codes",
                "bad_distractors",
            ],
        )
        writer.writeheader()
        writer.writerows(csv_rows)

    print("===== MIXED CHOICE LAYER AUDIT SUMMARY =====")
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    print("\n===== FIRST 40 SUSPICIOUS ITEMS =====")
    for row in suspicious_items[:40]:
        print(json.dumps(row, ensure_ascii=False))
    print("\n===== OUTPUT FILES =====")
    print(str(OUT_JSON))
    print(str(OUT_CSV))

    conn.close()

if __name__ == "__main__":
    main()
