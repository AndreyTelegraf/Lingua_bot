from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

ROOT = Path("/home/andrey/Projects/lingua_bot_v2")
DB = ROOT / "data/lingua_staging.db"
ART = ROOT / "artifacts"
MAP_PATH = ROOT / "data/manual/noun_manual_ru_map_v2.json"

GENERIC_POOL = [
    "часть","форма","случай","вопрос","ответ","слово","время","день","год","ночь","уровень","система",
    "процесс","результат","группа","лицо","сторона","линия","режим","значение","эффект","имя","город",
    "страна","семья","рынок","мир","страх","сила","закон","центр","причина","пример","начало","конец",
    "место","публика","вкус","основа","речь","прошлое","право","час","власть","женщина","человек","никто",
    "фото","видео","плюс","минус","двойка","тройка","четвёрка","пятёрка","шестёрка","знание","счёт",
    "доступ","сердце","список","пространство","поддержка","возраст","зал","совет","встреча","тема",
    "церковь","позиция","начальник","поиск","интерес","суд","еда","возможность","код","высота","выбор",
    "премия","разница","стиль","лидер","остаток","визит","разум","природа","отдел","земля","осторожность"
]

def norm(s: str) -> str:
    return " ".join((s or "").strip().lower().split())

def latest_shortlist_dir() -> Path:
    dirs = sorted(ART.glob("noun_shortlist_v2_*"), reverse=True)
    if not dirs:
        raise FileNotFoundError("noun_shortlist_v2 artifact not found")
    return dirs[0]

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

def existing_lemma_pos(conn: sqlite3.Connection) -> set[tuple[str, str]]:
    rows = conn.execute("SELECT lower(trim(lemma)), pos FROM vocab_items").fetchall()
    return {(str(a), str(b)) for a, b in rows}

def build_question(lemma: str) -> str:
    return f"Что значит это слово?\\n\\n{lemma}"

def build_choices(correct: str) -> list[str]:
    out = [correct]
    for x in GENERIC_POOL:
        if norm(x) != norm(correct) and x not in out:
            out.append(x)
        if len(out) == 6:
            break
    if len(out) != 6 or len(set(out)) != 6:
        raise ValueError(f"bad choices for {correct}: {out}")
    return out

def insert_item(conn: sqlite3.Connection, *, lemma: str, freq_rank: int, correct: str, choices: list[str]) -> int:
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
    for idx, choice in enumerate(choices):
        row_payload: dict[str, object] = {}
        for col in choice_cols:
            if col == "item_id":
                row_payload[col] = item_id
            elif col == "choice_text":
                row_payload[col] = choice
            elif col == "is_correct":
                row_payload[col] = 1 if norm(choice) == norm(correct) else 0
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
    shortlist_dir = latest_shortlist_dir()
    shortlist = json.loads((shortlist_dir / "safe_shortlist.json").read_text(encoding="utf-8"))
    manual_map = json.loads(MAP_PATH.read_text(encoding="utf-8"))

    conn = sqlite3.connect(DB)
    existing = existing_lemma_pos(conn)
    before = active_state(conn)

    selected = []
    skipped = []

    for row in shortlist:
        lemma = row["lemma"]
        mapped = (manual_map.get(lemma) or "").strip()
        if not mapped:
            skipped.append({"lemma": lemma, "reason": "unmapped"})
            continue
        if (norm(lemma), "noun") in existing:
            skipped.append({"lemma": lemma, "reason": "already_present"})
            continue
        selected.append({
            "lemma": lemma,
            "freq_rank": int(row["freq_rank"]),
            "correct": mapped,
            "choices": build_choices(mapped),
        })

    inserted = []
    for row in selected:
        item_id = insert_item(
            conn,
            lemma=row["lemma"],
            freq_rank=row["freq_rank"],
            correct=row["correct"],
            choices=row["choices"],
        )
        inserted.append({
            "id": item_id,
            "lemma": row["lemma"],
            "correct_answer": row["correct"],
            "freq_rank": row["freq_rank"],
        })

    conn.commit()
    after = active_state(conn)
    struct = structural(conn)
    conn.close()

    outdir = ART / f"noun_remediation_apply_v2_{time.strftime('%Y%m%d_%H%M%S')}"
    outdir.mkdir(parents=True, exist_ok=True)

    report = {
        "shortlist_source": str(shortlist_dir / "safe_shortlist.json"),
        "manual_map_source": str(MAP_PATH),
        "selected_total": len(selected),
        "inserted_total": len(inserted),
        "skipped_total": len(skipped),
        "before_active_by_pos": before,
        "after_active_by_pos": after,
        "structural_status_after": struct,
        "inserted": inserted,
        "skipped": skipped
    }
    (outdir / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(outdir / "summary.json")

if __name__ == "__main__":
    main()
