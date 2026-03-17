from __future__ import annotations

import csv
import json
import sqlite3
import time
from pathlib import Path

ROOT = Path("/home/andrey/Projects/lingua_bot_v2")
DB = ROOT / "data/lingua_staging.db"
DRYRUN_DIRS = sorted(ROOT.glob("artifacts/vocab_bank_orchestrator_dryrun_*"))
if not DRYRUN_DIRS:
    raise SystemExit("no vocab_bank_orchestrator_dryrun artifact found")
DRYRUN = DRYRUN_DIRS[-1] / "summary.json"

OUT = ROOT / "artifacts" / f"vocab_bank_orchestrator_apply_v1_{time.strftime('%Y%m%d_%H%M%S')}"
OUT.mkdir(parents=True, exist_ok=True)

BAD_EXACT = {"должен", "иметь выгоду", "тренирова́ться"}
BAD_SUBSTR = {"тренирова"}

VERB_NEW_ALLOW = {
    "ir", "estar", "poder", "sair", "partir", "deixar", "passar", "chegar",
    "levar", "militar", "manter", "tirar", "conseguir", "criar", "colocar",
    "olhar", "vir", "haver", "governar",
}

ADVERB_NEW_ALLOW = {"tão", "aí", "embora", "inclusive"}

def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))

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

def table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [str(r[1]) for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]

def has_existing(conn: sqlite3.Connection, pos: str, lemma: str) -> tuple[bool, bool]:
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
        elif col == "created_at":
            payload[col] = "CURRENT_TIMESTAMP_SENTINEL"
        elif col == "updated_at":
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
            elif col == "created_at":
                row_payload[col] = "CURRENT_TIMESTAMP_SENTINEL"
            elif col == "updated_at":
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

def verb_choices(lemma: str) -> list[str]:
    packs = {
        "ir": ["идти", "возвращаться", "приходить", "входить", "выходить", "прибывать"],
        "estar": ["быть", "казаться", "оставаться", "видеть", "чувствовать", "находиться"],
        "poder": ["мочь", "знать", "делать", "сказать", "давать", "получать"],
        "sair": ["выходить", "входить", "возвращаться", "приходить", "ломаться", "убегать"],
        "partir": ["делить", "ломать", "переводить", "стрелять", "успеть", "принимать"],
        "deixar": ["уходить", "возвращаться", "проходить", "прибывать", "входить", "выходить"],
        "passar": ["проходить", "входить", "возвращаться", "приходить", "оставаться", "собирать"],
        "chegar": ["прибывать", "приходить", "уходить", "возвращаться", "входить", "выходить"],
        "levar": ["брать", "класть", "держать", "получать", "сохранять", "приносить"],
        "militar": ["бороться", "управлять", "смеяться", "просыпаться", "жениться", "смотреть"],
        "manter": ["сохранять", "брать", "держать", "класть", "принимать", "получать"],
        "tirar": ["брать", "класть", "получать", "сохранять", "входить", "выходить"],
        "conseguir": ["получать", "создавать", "класть", "смотреть", "управлять", "идти"],
        "criar": ["создавать", "получать", "брать", "смотреть", "управлять", "приходить"],
        "colocar": ["класть", "брать", "создавать", "получать", "входить", "выходить"],
        "olhar": ["смотреть", "видеть", "чувствовать", "замечать", "искать", "оставаться"],
        "vir": ["приходить", "идти", "возвращаться", "входить", "выходить", "прибывать"],
        "haver": ["иметься", "быть", "существовать", "находиться", "оставаться", "казаться"],
        "governar": ["управлять", "бороться", "создавать", "держать", "смеяться", "смотреть"],
    }
    return packs[lemma]

def adverb_choices(lemma: str) -> list[str]:
    packs = {
        "tão": ["так", "очень", "точно", "сейчас", "довольно", "меньше"],
        "aí": ["там", "тогда", "сейчас", "точно", "снова", "довольно"],
        "embora": ["прочь", "там", "тогда", "снова", "точно", "сейчас"],
        "inclusive": ["тоже", "очень", "снова", "точно", "сейчас", "однако"],
    }
    return packs[lemma]

def main() -> None:
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    assert_green(conn, "pre_apply")

    verb_seed = {
        str(r["lemma"]).strip().lower(): r
        for r in read_csv(ROOT / "data/sources/pilot_ptpt_002_verbs_builder_seed.csv")
    }
    adverb_seed = {
        str(r["lemma"]).strip().lower(): r
        for r in read_csv(ROOT / "data/sources/pilot_ptpt_004_adverbs_builder_seed.csv")
    }

    before = active_by_pos(conn)
    inserted = []

    for lemma in sorted(VERB_NEW_ALLOW):
        has_active, has_inactive = has_existing(conn, "verb", lemma)
        if has_active or has_inactive:
            continue
        row = verb_seed[lemma]
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
        inserted.append({"pos": "verb", "lemma": lemma, "id": item_id, "correct": ru_gloss})

    for lemma in sorted(ADVERB_NEW_ALLOW):
        has_active, has_inactive = has_existing(conn, "adverb", lemma)
        if has_active or has_inactive:
            continue
        row = adverb_seed[lemma]
        ru_gloss = str(row["ru_gloss"]).strip()
        freq_rank = int(str(row["freq_rank"]).strip())
        choices = adverb_choices(lemma)
        validate_choices(choices, ru_gloss)
        item_id = insert_item_with_choices(
            conn,
            lemma=lemma,
            pos="adverb",
            freq_rank=freq_rank,
            ru_gloss=ru_gloss,
            choices=choices,
        )
        activate_item(conn, item_id)
        inserted.append({"pos": "adverb", "lemma": lemma, "id": item_id, "correct": ru_gloss})

    conn.commit()
    assert_green(conn, "post_apply")

    summary = {
        "dryrun_source": str(DRYRUN),
        "before_active_by_pos": before,
        "after_active_by_pos": active_by_pos(conn),
        "inserted_total": len(inserted),
        "inserted": inserted,
        "structural_status_after": structural_status(conn),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(OUT / "summary.json")

if __name__ == "__main__":
    main()
