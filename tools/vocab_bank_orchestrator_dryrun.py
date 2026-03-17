from __future__ import annotations

import csv
import json
import sqlite3
import sys
import time
from pathlib import Path


ROOT = Path("/home/andrey/Projects/lingua_bot_v2")
DB = ROOT / "data/lingua_staging.db"
OUT = ROOT / "artifacts" / f"vocab_bank_orchestrator_dryrun_{time.strftime('%Y%m%d_%H%M%S')}"
OUT.mkdir(parents=True, exist_ok=True)

POS_CONFIG = {
    "noun": {
        "seed_csv": ROOT / "data/sources/pilot_ptpt_001_nouns_external_clean.csv",
    },
    "verb": {
        "seed_csv": ROOT / "data/sources/pilot_ptpt_002_verbs_builder_seed.csv",
    },
    "adjective": {
        "seed_csv": ROOT / "data/sources/pilot_ptpt_003_adjectives_builder_seed.csv",
    },
    "adverb": {
        "seed_csv": ROOT / "data/sources/pilot_ptpt_004_adverbs_builder_seed.csv",
    },
}

BAD_EXACT = {"должен", "иметь выгоду", "тренирова́ться"}
BAD_SUBSTR = {"тренирова"}


def read_csv_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def get_active_pos_distribution(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute(
        """
        SELECT pos, COUNT(*) AS cnt
        FROM vocab_items
        WHERE is_active = 1
        GROUP BY pos
        ORDER BY pos
        """
    ).fetchall()
    return {str(r[0]): int(r[1]) for r in rows}


def get_structural_status(conn: sqlite3.Connection) -> dict[str, int]:
    row = conn.execute(
        """
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
        """
    ).fetchone()
    return {
        "active_zero_choices": int(row[0] or 0),
        "active_not_6_choices": int(row[1] or 0),
        "active_not_1_correct": int(row[2] or 0),
        "active_not_6_distinct_choices": int(row[3] or 0),
    }


def normalize_lemma(x: str) -> str:
    return (x or "").strip().lower()


def count_existing(conn: sqlite3.Connection, pos: str, lemma: str) -> tuple[bool, bool]:
    row = conn.execute(
        """
        SELECT
          MAX(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) AS has_active,
          MAX(CASE WHEN is_active = 0 THEN 1 ELSE 0 END) AS has_inactive
        FROM vocab_items
        WHERE pos = ? AND lower(trim(lemma)) = lower(trim(?))
        """,
        (pos, lemma),
    ).fetchone()
    return bool(row[0]), bool(row[1])


def classify_row(pos: str, row: dict, conn: sqlite3.Connection) -> dict:
    lemma = normalize_lemma(row.get("lemma", ""))
    ru_gloss = (row.get("ru_gloss") or "").strip()
    freq_rank_raw = (row.get("freq_rank") or "").strip()
    try:
        freq_rank = int(freq_rank_raw) if freq_rank_raw else 999999
    except ValueError:
        freq_rank = 999999

    has_active, has_inactive = count_existing(conn, pos, lemma)

    issues: list[str] = []
    if not lemma:
        issues.append("missing_lemma")
    if not ru_gloss:
        issues.append("missing_ru_gloss")
    if ru_gloss.lower() in BAD_EXACT:
        issues.append(f"bad_gloss_exact:{ru_gloss.lower()}")
    if any(s in ru_gloss.lower() for s in BAD_SUBSTR):
        issues.append(f"bad_gloss_substr:{ru_gloss.lower()}")

    if has_active:
        status = "already_active"
    elif has_inactive:
        status = "inactive_candidate_exists"
    elif issues:
        status = "needs_remediation"
    else:
        status = "safe_new_candidate"

    return {
        "lemma": lemma,
        "pos": pos,
        "freq_rank": freq_rank,
        "ru_gloss": ru_gloss,
        "source_file": row.get("source_file") or "",
        "gloss_source": row.get("gloss_source") or "",
        "status": status,
        "issues": issues,
    }


def summarize_pos(pos: str, rows: list[dict], conn: sqlite3.Connection) -> dict:
    classified = [classify_row(pos, row, conn) for row in rows]

    counts = {
        "raw_total": len(rows),
        "safe_new_candidate": 0,
        "inactive_candidate_exists": 0,
        "already_active": 0,
        "needs_remediation": 0,
    }
    for r in classified:
        counts[r["status"]] += 1

    safe_rows = sorted(
        [r for r in classified if r["status"] == "safe_new_candidate"],
        key=lambda x: (x["freq_rank"], x["lemma"]),
    )
    remediation_rows = sorted(
        [r for r in classified if r["status"] == "needs_remediation"],
        key=lambda x: (x["freq_rank"], x["lemma"]),
    )

    activation_candidates = sorted(
        [r for r in classified if r["status"] in {"safe_new_candidate", "inactive_candidate_exists"}],
        key=lambda x: (x["freq_rank"], x["lemma"]),
    )

    return {
        "pos": pos,
        "seed_csv": str(POS_CONFIG[pos]["seed_csv"]),
        "counts": counts,
        "top_safe_new_candidates": safe_rows[:25],
        "top_needs_remediation": remediation_rows[:25],
        "top_activation_candidates": activation_candidates[:25],
    }


def main() -> None:
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    pos_reports = {}
    for pos, cfg in POS_CONFIG.items():
        rows = read_csv_rows(cfg["seed_csv"])
        pos_reports[pos] = summarize_pos(pos, rows, conn)

    summary = {
        "db": str(DB),
        "active_pos_distribution": get_active_pos_distribution(conn),
        "structural_status": get_structural_status(conn),
        "pos_reports": pos_reports,
        "notes": [
            "Dry-run only: no DB mutations performed.",
            "safe_new_candidate = clean seed row with no existing active/inactive match.",
            "inactive_candidate_exists = candidate likely ready for later selective activation.",
            "needs_remediation = missing gloss or blocked gloss pattern.",
        ],
    }

    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(OUT / "summary.json")


if __name__ == "__main__":
    main()
