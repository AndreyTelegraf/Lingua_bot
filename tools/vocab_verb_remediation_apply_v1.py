from __future__ import annotations

import csv
import json
import sqlite3
import time
from pathlib import Path

ROOT = Path("/home/andrey/Projects/lingua_bot_v2")
DB = ROOT / "data/lingua_staging.db"
OUT = ROOT / "artifacts" / f"verb_remediation_apply_v1_{time.strftime('%Y%m%d_%H%M%S')}"
OUT.mkdir(parents=True, exist_ok=True)

MANUAL_REMEDIATION = {
    "jogar": {
        "ru_gloss": "играть",
        "en_gloss": "to play (to participate in a sport or game)",
        "freq_rank": 2970,
    }
}

BAD_EXACT = {"должен", "иметь выгоду", "тренирова́ться"}
BAD_SUBSTR = {"тренирова"}

def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))

def table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [str(r[1]) for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]

def structural_status(conn: sqlite3.Connection) -> dict[str, int]:
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

def assert_green(conn: sqlite3.Connection, stage: str) -> None:
    st = structural_status(conn)
    if any(st.values()):
        raise SystemExit(f"{stage}: active bank is not structurally green: {st}")

def active_by_pos(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute(
        "SELECT pos, COUNT(*) FROM vocab_items WHERE is_active = 1 GROUP BY pos ORDER BY pos"
    ).fetchall()
    return {str(r[0]): int(r[1]) for r in rows}

def build_question(lemma: str) -> str:
    return f"Что значит это слово?\n\n{lemma}"

def validate_choices(choices: list[str], correct: str) -> None:
    if len(choices) != 6:
        raise ValueError(f"bad choices len: {choices}")
    if len(set(choices)) != 6:
        raise ValueError(f"non-distinct choices: {choices}")
    if correct not in choices:
        raise ValueError(f"correct missing in choices: {correct}")
    for c in choices:
        low = c.lower()
        if low in BAD_EXACT:
            raise ValueError(f"bad exact choice: {c}")
        if any(s in low for s in BAD_SUBSTR):
            raise ValueError(f"bad substr choice: {c}")

def insert_item_with_choices(
    conn: sqlite3.Connection,
    *,
    lemma: str,
    pos: str,
    freq_rank: int,
    ru_gloss: str,
    choices: list[str],
) -> int:
    item_cols = table_columns(conn, "vocab_items")
    payload: dict[str, object] = {}
    for col in item_cols:
        if col == "lemma":
            payload[col] = lemma
        elif col == "pos":
            payload[col] = pos
        elif col == "freq_rank":
            payload[col] = freq_rank
        elif col == "question_text":
            payload[col] = build_question(lemma)
        elif col == "correct_answer":
            payload[col] = ru_gloss
        elif col == "is_active":
            payload[col] = 0
        elif col == "source_type":
            payload[col] = "manual_review_high"
        elif col in {"created_at", "updated_at"}:
            payload[col] = "CURRENT_TIMESTAMP_SENTINEL"

    cols = list(payload.keys())
    value_sql = []
    value_args = []
    for c in cols:
        if payload[c] == "CURRENT_TIMESTAMP_SENTINEL":
            value_sql.append("CURRENT_TIMESTAMP")
        else:
            value_sql.append("?")
            value_args.append(payload[c])

    conn.execute(
        f"INSERT INTO vocab_items ({','.join(cols)}) VALUES ({','.join(value_sql)})",
        value_args,
    )
    item_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])

    choice_cols = table_columns(conn, "vocab_choices")
    for idx, text in enumerate(choices):
        row_payload: dict[str, object] = {}
        for col in choice_cols:
            if col == "item_id":
                row_payload[col] = item_id
            elif col == "choice_text":
                row_payload[col] = text
            elif col == "is_correct":
                row_payload[col] = 1 if text == ru_gloss else 0
            elif col == "position_index":
                row_payload[col] = idx
            elif col in {"created_at", "updated_at"}:
                row_payload[col] = "CURRENT_TIMESTAMP_SENTINEL"

        cols2 = list(row_payload.keys())
        value_sql2 = []
        value_args2 = []
        for c in cols2:
            if row_payload[c] == "CURRENT_TIMESTAMP_SENTINEL":
                value_sql2.append("CURRENT_TIMESTAMP")
            else:
                value_sql2.append("?")
                value_args2.append(row_payload[c])

        conn.execute(
            f"INSERT INTO vocab_choices ({','.join(cols2)}) VALUES ({','.join(value_sql2)})",
            value_args2,
        )
    return item_id

def activate_item(conn: sqlite3.Connection, item_id: int) -> None:
    conn.execute(
        "UPDATE vocab_items SET is_active = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (item_id,),
    )

def find_existing(conn: sqlite3.Connection, lemma: str) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT id, lemma, is_active, correct_answer
        FROM vocab_items
        WHERE pos = 'verb' AND lower(trim(lemma)) = lower(trim(?))
        ORDER BY is_active DESC, id DESC
        LIMIT 1
        """,
        (lemma,),
    ).fetchone()

def verb_choices(lemma: str) -> list[str]:
    packs = {
        "jogar": ["играть", "смеяться", "смотреть", "создавать", "получать", "бороться"],
    }
    return packs[lemma]

def remaining_safe_candidates(conn: sqlite3.Connection, seed_rows: dict[str, dict]) -> list[dict]:
    out = []
    for lemma, row in sorted(seed_rows.items()):
        existing = find_existing(conn, lemma)
        if existing is not None and int(existing["is_active"] or 0) == 1:
            continue
        if not str(row.get("ru_gloss", "")).strip():
            continue
        out.append({
            "lemma": lemma,
            "freq_rank": int(str(row["freq_rank"]).strip()),
            "ru_gloss": str(row["ru_gloss"]).strip(),
            "status": "candidate",
        })
    return out

def main() -> None:
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    assert_green(conn, "pre_apply")

    seed_rows = {
        str(r["lemma"]).strip().lower(): r
        for r in read_csv(ROOT / "data/sources/pilot_ptpt_002_verbs_builder_seed.csv")
    }

    for lemma, data in MANUAL_REMEDIATION.items():
        if lemma not in seed_rows:
            seed_rows[lemma] = {
                "lemma": lemma,
                "pos": "verb",
                "freq_rank": str(data["freq_rank"]),
                "ru_gloss": data["ru_gloss"],
                "en_gloss": data["en_gloss"],
                "gloss_source": "manual_remediation_v2",
                "source_file": "manual_remediation_v2",
                "zipf_pt": "",
            }
        else:
            seed_rows[lemma]["ru_gloss"] = data["ru_gloss"]
            seed_rows[lemma]["en_gloss"] = data["en_gloss"]
            seed_rows[lemma]["gloss_source"] = "manual_remediation_v2"

    before = active_by_pos(conn)
    inserted = []
    activated_existing = []
    skipped = []

    for lemma in sorted(MANUAL_REMEDIATION.keys()):
        existing = find_existing(conn, lemma)
        if existing is not None:
            if int(existing["is_active"] or 0) == 1:
                skipped.append({"lemma": lemma, "reason": "already_active", "id": int(existing["id"])})
                continue
            activate_item(conn, int(existing["id"]))
            activated_existing.append({"lemma": lemma, "id": int(existing["id"])})
            continue

        row = seed_rows[lemma]
        ru_gloss = str(row["ru_gloss"]).strip()
        freq_rank = int(str(row["freq_rank"]).strip())
        choices = verb_choices(lemma)
        validate_choices(choices, ru_gloss)

        item_id = insert_item_with_choices(
            conn,
            lemma=lemma,
            pos="verb",
            freq_rank=freq_rank,
            ru_gloss=ru_gloss,
            choices=choices,
        )
        activate_item(conn, item_id)
        inserted.append({"lemma": lemma, "id": item_id, "correct": ru_gloss})

    conn.commit()
    assert_green(conn, "post_apply")

    remaining = remaining_safe_candidates(conn, seed_rows)

    summary = {
        "before_active_by_pos": before,
        "after_active_by_pos": active_by_pos(conn),
        "inserted_total": len(inserted),
        "activated_existing_total": len(activated_existing),
        "skipped_total": len(skipped),
        "inserted": inserted,
        "activated_existing": activated_existing,
        "skipped": skipped,
        "remaining_safe_candidates_total": len(remaining),
        "remaining_safe_candidates_top": remaining[:25],
        "structural_status_after": structural_status(conn),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(OUT / "summary.json")

if __name__ == "__main__":
    main()
