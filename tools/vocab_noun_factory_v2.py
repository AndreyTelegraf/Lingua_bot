from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import time
from pathlib import Path

ROOT = Path("/home/andrey/Projects/lingua_bot_v2")
DB = ROOT / "data/lingua_staging.db"
SRC = ROOT / "data/sources/pilot_ptpt_001_nouns_external_clean.csv"
ART = ROOT / "artifacts"

BAD_SUBSTR = [
    "plural of ",
    "feminine of ",
    "masculine of ",
    "alternative form of ",
    "ellipsis of ",
    "nickname",
    "letter ",
    "script letter",
    "pre-reform spelling",
    "misspelling",
    "obsolete spelling",
    "surname",
    "slavic tribe",
    "municipality",
    "river in ",
    "river god",
    "world wide web",
    "greeting",
    "good morning",
    "good afternoon",
    "good evening",
    "new year",
    "afterlife",
    "beyond",
]

MANUAL_RU = {
    "mais": "плюс",
    "ser": "существо",
    "são": "здоровый человек",
    "grande": "важная персона",
    "dois": "двойка",
    "nunca": "никогда",
    "todo": "целое",
    "novo": "новинка",
    "primeiro": "первый",
    "menos": "минус",
    "alguém": "человек",
    "falar": "говор",
    "tinha": "стригущий лишай",
    "boa": "хорошая новость",
    "três": "тройка",
    "meio": "середина",
    "mulher": "женщина",
    "ninguém": "никто",
    "foto": "фото",
    "saber": "знание",
    "conta": "счёт",
    "final": "конец",
    "hora": "час",
    "filho": "сын",
    "vídeo": "видео",
    "vão": "проём",
    "poder": "власть",
    "frente": "передняя часть",
    "tarde": "день",
    "local": "место",
    "público": "публика",
    "centro": "центр",
    "logo": "логотип",
    "feito": "поступок",
    "exemplo": "пример",
    "falta": "нехватка",
    "série": "серия",
    "causa": "причина",
    "uso": "использование",
    "cerca": "забор",
    "cinco": "пятёрка",
    "início": "начало",
    "claro": "просвет",
    "atenção": "внимание",
    "gosto": "вкус",
    "base": "основа",
    "fala": "речь",
    "passado": "прошлое",
}

GENERIC_POOL = [
    "часть","форма","случай","вопрос","ответ","слово","время","день","год","ночь","уровень","система",
    "процесс","результат","группа","лицо","сторона","линия","режим","значение","эффект","имя","город",
    "страна","семья","рынок","мир","страх","сила","закон","центр","причина","пример","начало","конец",
    "место","публика","вкус","основа","речь","прошлое","право","час","власть","женщина","человек","никто",
    "фото","видео","плюс","минус","двойка","тройка","пятёрка","знание","счёт","серия","использование",
]

def norm(s: str) -> str:
    return " ".join((s or "").strip().lower().split())

def table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [str(r[1]) for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]

def existing_lemma_pos(conn: sqlite3.Connection) -> set[tuple[str, str]]:
    rows = conn.execute("SELECT lower(trim(lemma)), pos FROM vocab_items").fetchall()
    return {(str(a), str(b)) for a, b in rows}

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

def classify(row: dict[str, str], existing: set[tuple[str, str]]) -> str:
    lemma = row["lemma"]
    gloss = row["ru_gloss"]
    if (norm(lemma), "noun") in existing:
        return "already_present"
    if lemma not in MANUAL_RU:
        return "skip_unmapped"
    low = norm(gloss)
    if any(x in low for x in BAD_SUBSTR):
        return "skip_blocked_source"
    if "-" in lemma or lemma[:1].isupper() or len(lemma) <= 2:
        return "skip_shape_risk"
    return "candidate"

def build_choices(correct: str) -> list[str]:
    choices = [correct]
    for item in GENERIC_POOL:
        if norm(item) != norm(correct) and item not in choices:
            choices.append(item)
        if len(choices) == 6:
            break
    if len(choices) != 6 or len(set(choices)) != 6:
        raise ValueError(f"bad noun choices for {correct}: {choices}")
    return choices

def insert_item(conn: sqlite3.Connection, lemma: str, freq_rank: int, correct: str, choices: list[str], *, activate: bool) -> int:
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
            payload[col] = 1 if activate else 0
        elif col == "source_type":
            payload[col] = "manual_review_high"
        elif col in ("created_at", "updated_at"):
            payload[col] = "__NOW__"

    cols = list(payload.keys())
    sql_vals, args = [], []
    for c in cols:
        if payload[c] == "__NOW__":
            sql_vals.append("CURRENT_TIMESTAMP")
        else:
            sql_vals.append("?")
            args.append(payload[c])

    conn.execute(
        "INSERT INTO vocab_items ({}) VALUES ({})".format(",".join(cols), ",".join(sql_vals)),
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
        sql_vals2, args2 = [], []
        for c in cols2:
            if row_payload[c] == "__NOW__":
                sql_vals2.append("CURRENT_TIMESTAMP")
            else:
                sql_vals2.append("?")
                args2.append(row_payload[c])

        conn.execute(
            "INSERT INTO vocab_choices ({}) VALUES ({})".format(",".join(cols2), ",".join(sql_vals2)),
            args2,
        )

    return item_id

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", required=True, choices=["dryrun", "apply"])
    ap.add_argument("--limit", type=int, default=150)
    args = ap.parse_args()

    outdir = ART / f"noun_factory_v2_{args.mode}_{time.strftime('%Y%m%d_%H%M%S')}"
    outdir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB)
    existing = existing_lemma_pos(conn)

    candidates, skipped = [], []
    with SRC.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            row = {
                "lemma": (raw.get("lemma") or "").strip(),
                "pos": (raw.get("pos") or "").strip(),
                "freq_rank": int((raw.get("freq_rank") or "999999").strip() or "999999"),
                "ru_gloss": (raw.get("ru_gloss") or "").strip(),
                "source_file": (raw.get("source_file") or "").strip(),
            }
            if row["pos"] != "noun":
                continue
            status = classify(row, existing)
            if status == "candidate":
                lemma = row["lemma"]
                candidates.append({
                    "lemma": lemma,
                    "pos": "noun",
                    "freq_rank": row["freq_rank"],
                    "ru_gloss": MANUAL_RU[lemma],
                    "choices": build_choices(MANUAL_RU[lemma]),
                    "source_file": row["source_file"],
                })
            else:
                skipped.append({"lemma": row["lemma"], "freq_rank": row["freq_rank"], "status": status})

    candidates.sort(key=lambda x: (x["freq_rank"], x["lemma"]))
    selected = candidates[: args.limit]

    before = active_state(conn)
    inserted = []

    if args.mode == "apply":
        for row in selected:
            item_id = insert_item(
                conn,
                row["lemma"],
                row["freq_rank"],
                row["ru_gloss"],
                row["choices"],
                activate=True,
            )
            inserted.append({
                "id": item_id,
                "lemma": row["lemma"],
                "correct_answer": row["ru_gloss"],
                "freq_rank": row["freq_rank"],
            })
        conn.commit()

    after = active_state(conn)
    struct = structural(conn)
    conn.close()

    report = {
        "mode": args.mode,
        "limit": args.limit,
        "candidate_total": len(candidates),
        "selected_total": len(selected),
        "skipped_total": len(skipped),
        "before_active_by_pos": before,
        "after_active_by_pos": after,
        "structural_status_after": struct,
        "selected_preview": selected[:50],
        "inserted_total": len(inserted),
        "inserted": inserted[:200],
        "skipped_preview": skipped[:100],
    }

    (outdir / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(outdir / "summary.json")

if __name__ == "__main__":
    main()
