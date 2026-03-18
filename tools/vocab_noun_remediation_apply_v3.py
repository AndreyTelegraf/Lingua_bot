from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

ROOT = Path("/home/andrey/Projects/lingua_bot_v2")
DB = ROOT / "data/lingua_staging.db"
ART = ROOT / "artifacts"
SHORTLIST = max((ROOT / "artifacts").glob("noun_bulk_prep_v3_*/safe_shortlist_v3.json"), key=lambda p: p.stat().st_mtime)
MANUAL_MAP = ROOT / "data/manual/noun_manual_ru_map_v3.json"

GENERIC_POOL = [
    "часть","форма","случай","вопрос","ответ","слово","время","день","год","ночь","уровень","система",
    "процесс","результат","группа","лицо","сторона","линия","режим","значение","эффект","имя","город",
    "страна","семья","рынок","мир","страх","сила","закон","центр","причина","пример","начало","конец",
    "место","публика","вкус","основа","речь","прошлое","право","час","власть","женщина","человек","никто",
    "фото","видео","плюс","минус","двойка","тройка","пятёрка","знание","счёт","серия","использование",
    "вчерашний день","шестёрка","завтра","машина","верх","дно","источник","полоса","факультет","удача",
    "разрез","след","зрение"
]

def norm(s: str) -> str:
    return " ".join((s or "").strip().lower().split())

def table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [str(r[1]) for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]

def active_state(conn: sqlite3.Connection) -> dict[str, int]:
    return dict(conn.execute(
        "SELECT pos, COUNT(*) FROM vocab_items WHERE is_active = 1 GROUP BY pos ORDER BY pos"
    ).fetchall())

def structural(conn: sqlite3.Connection) -> dict[str, int]:
    row = conn.execute("""
    WITH s AS (
      SELECT
        vi.id,
        COUNT(vc.id) AS choice_count,
        SUM(CASE WHEN vc.is_correct = 1 THEN 1 ELSE 0 END) AS correct_count,
        COUNT(DISTINCT vc.choice_text) AS distinct_count
      FROM vocab_items vi
      LEFT JOIN vocab_choices vc ON vc.item_id = vi.id
      WHERE vi.is_active = 1
      GROUP BY vi.id
    )
    SELECT
      SUM(CASE WHEN choice_count = 0 THEN 1 ELSE 0 END),
      SUM(CASE WHEN choice_count != 6 THEN 1 ELSE 0 END),
      SUM(CASE WHEN correct_count != 1 THEN 1 ELSE 0 END),
      SUM(CASE WHEN distinct_count != 6 THEN 1 ELSE 0 END)
    FROM s
    """).fetchone()
    return {
        "active_zero_choices": int(row[0] or 0),
        "active_not_6_choices": int(row[1] or 0),
        "active_not_1_correct": int(row[2] or 0),
        "active_not_6_distinct_choices": int(row[3] or 0),
    }

def build_question(lemma: str) -> str:
    return f"Что значит это слово?\n\n{lemma}"

def build_choices(correct: str) -> list[str]:
    choices = [correct]
    for item in GENERIC_POOL:
        if norm(item) != norm(correct) and item not in choices:
            choices.append(item)
        if len(choices) == 6:
            break
    if len(choices) != 6 or len(set(choices)) != 6:
        raise ValueError(f"bad choices for {correct}: {choices}")
    return choices

def existing_noun_ids(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute(
        "SELECT lower(trim(lemma)), id FROM vocab_items WHERE pos = 'noun'"
    ).fetchall()
    return {str(a): int(b) for a, b in rows}

def insert_item(conn: sqlite3.Connection, lemma: str, freq_rank: int, correct: str, choices: list[str]) -> int:
    item_cols = table_columns(conn, "vocab_items")
    payload: dict[str, object] = {}
    for col in item_cols:
        if col == "lemma":
            payload[col] = lemma
        elif col == "pos":
            payload[col] = "noun"
        elif col == "freq_rank":
            payload[col] = freq_rank
        elif col == "question_text":
            payload[col] = build_question(lemma)
        elif col == "correct_answer":
            payload[col] = correct
        elif col == "is_active":
            payload[col] = 1
        elif col == "source_type":
            payload[col] = "manual_review_high"
        elif col in ("created_at", "updated_at"):
            payload[col] = "__NOW__"

    cols = list(payload.keys())
    vals_sql, args = [], []
    for c in cols:
        if payload[c] == "__NOW__":
            vals_sql.append("CURRENT_TIMESTAMP")
        else:
            vals_sql.append("?")
            args.append(payload[c])

    conn.execute(
        "INSERT INTO vocab_items ({}) VALUES ({})".format(",".join(cols), ",".join(vals_sql)),
        args,
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
                row_payload[col] = 1 if norm(text) == norm(correct) else 0
            elif col == "position_index":
                row_payload[col] = idx
            elif col in ("created_at", "updated_at"):
                row_payload[col] = "__NOW__"

        cols2 = list(row_payload.keys())
        vals_sql2, args2 = [], []
        for c in cols2:
            if row_payload[c] == "__NOW__":
                vals_sql2.append("CURRENT_TIMESTAMP")
            else:
                vals_sql2.append("?")
                args2.append(row_payload[c])

        conn.execute(
            "INSERT INTO vocab_choices ({}) VALUES ({})".format(",".join(cols2), ",".join(vals_sql2)),
            args2,
        )

    return item_id

def main() -> None:
    shortlist = json.loads(SHORTLIST.read_text(encoding="utf-8"))
    manual_map = json.loads(MANUAL_MAP.read_text(encoding="utf-8"))

    outdir = ART / f"noun_remediation_apply_v3_{time.strftime('%Y%m%d_%H%M%S')}"
    outdir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB)
    before = active_state(conn)
    present = existing_noun_ids(conn)

    inserted = []
    skipped = []

    for row in shortlist:
        lemma = row["lemma"]
        freq_rank = int(row["freq_rank"])
        mapped = (manual_map.get(lemma) or "").strip()

        if not mapped:
            skipped.append({"lemma": lemma, "reason": "unmapped"})
            continue

        if norm(lemma) in present:
            skipped.append({"lemma": lemma, "reason": "already_present", "id": present[norm(lemma)]})
            continue

        item_id = insert_item(conn, lemma, freq_rank, mapped, build_choices(mapped))
        inserted.append({
            "id": item_id,
            "lemma": lemma,
            "correct_answer": mapped,
            "freq_rank": freq_rank,
        })

    conn.commit()
    after = active_state(conn)
    struct = structural(conn)
    conn.close()

    report = {
        "shortlist_source": str(SHORTLIST),
        "manual_map_source": str(MANUAL_MAP),
        "selected_total": len(shortlist),
        "inserted_total": len(inserted),
        "skipped_total": len(skipped),
        "before_active_by_pos": before,
        "after_active_by_pos": after,
        "structural_status_after": struct,
        "inserted": inserted,
        "skipped": skipped,
    }
    (outdir / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(outdir / "summary.json")

if __name__ == "__main__":
    main()
