from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

ROOT = Path("/home/andrey/Projects/lingua_bot_v2")
DB = ROOT / "data/lingua_staging.db"
OUT = ROOT / "artifacts" / f"vocab_prod_readiness_report_{time.strftime('%Y%m%d_%H%M%S')}"
OUT.mkdir(parents=True, exist_ok=True)

def q1(conn: sqlite3.Connection, sql: str, args=()):
    row = conn.execute(sql, args).fetchone()
    return row[0] if row else None

def main() -> None:
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    active_by_pos = {
        str(r["pos"]): int(r["cnt"])
        for r in conn.execute("""
            SELECT pos, COUNT(*) AS cnt
            FROM vocab_items
            WHERE is_active = 1
            GROUP BY pos
            ORDER BY pos
        """).fetchall()
    }

    broken = conn.execute("""
        SELECT
          SUM(CASE WHEN choice_cnt = 0 THEN 1 ELSE 0 END) AS active_zero_choices,
          SUM(CASE WHEN choice_cnt != 6 THEN 1 ELSE 0 END) AS active_not_6_choices,
          SUM(CASE WHEN correct_cnt != 1 THEN 1 ELSE 0 END) AS active_not_1_correct,
          SUM(CASE WHEN distinct_cnt != 6 THEN 1 ELSE 0 END) AS active_not_6_distinct_choices
        FROM (
          SELECT
            vi.id,
            COUNT(vc.id) AS choice_cnt,
            SUM(CASE WHEN vc.is_correct = 1 THEN 1 ELSE 0 END) AS correct_cnt,
            COUNT(DISTINCT vc.choice_text) AS distinct_cnt
          FROM vocab_items vi
          LEFT JOIN vocab_choices vc ON vc.item_id = vi.id
          WHERE vi.is_active = 1
          GROUP BY vi.id
        )
    """).fetchone()

    duplicates = q1(conn, """
        SELECT COUNT(*)
        FROM (
          SELECT lower(trim(lemma)) AS lemma_norm, pos, COUNT(*) AS cnt
          FROM vocab_items
          WHERE is_active = 1
          GROUP BY lower(trim(lemma)), pos
          HAVING COUNT(*) > 1
        )
    """)

    total_active = sum(active_by_pos.values())
    noun = active_by_pos.get("noun", 0)
    adjective = active_by_pos.get("adjective", 0)
    adverb = active_by_pos.get("adverb", 0)
    verb = active_by_pos.get("verb", 0)

    shares = {
        "noun_share": round(noun / total_active, 4) if total_active else 0.0,
        "adjective_share": round(adjective / total_active, 4) if total_active else 0.0,
        "adverb_share": round(adverb / total_active, 4) if total_active else 0.0,
        "verb_share": round(verb / total_active, 4) if total_active else 0.0,
    }

    structurally_green = not any(int(broken[k] or 0) for k in broken.keys()) and int(duplicates or 0) == 0

    heuristic = {
        "structurally_green": structurally_green,
        "verb_floor_180": verb >= 180,
        "adverb_floor_90": adverb >= 90,
        "adjective_floor_220": adjective >= 220,
        "noun_cap_dominance_warn": noun / total_active <= 0.78 if total_active else False,
    }

    if all(heuristic.values()):
        decision = "GO_FOR_CONTROLLED_PROD_ROLLOUT"
    elif structurally_green:
        decision = "SOFT_GO_WITH_KNOWN_BANK_IMBALANCE"
    else:
        decision = "NO_GO"

    report = {
        "db": str(DB),
        "active_total": total_active,
        "active_by_pos": active_by_pos,
        "shares": shares,
        "broken": {k: int(broken[k] or 0) for k in broken.keys()},
        "duplicate_active_lemma_pos_count": int(duplicates or 0),
        "heuristic": heuristic,
        "decision": decision,
        "notes": [
            "This is a product-readiness heuristic report, not a psychometric certification.",
            "Safe verb backlog is closed.",
            "Safe adverb backlog is closed.",
            "Adjective layer improved but may still be shallower than noun layer.",
            "Noun layer remains dominant by design and source availability."
        ],
    }

    (OUT / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(OUT / "summary.json")

if __name__ == "__main__":
    main()
