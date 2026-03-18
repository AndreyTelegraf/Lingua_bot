from __future__ import annotations

import csv
import json
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path("/home/andrey/Projects/lingua_bot_v2")
DB = ROOT / "data/lingua_staging.db"
SRC = ROOT / "data/sources/pilot_ptpt_001_nouns_external_clean.csv"
ART = ROOT / "artifacts"

BAD_EXACT = {
    "", "-", "—", "?", "??", "n/a", "null",
}
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
    "eye dialect",
    "abbreviation",
    "suffix",
]

MANUAL_RU = {
    "pelo": "волос",
    "mesmo": "то же самое",
    "tudo": "всё",
    "agora": "настоящее время",
    "era": "эра",
    "vez": "раз",
    "coisa": "вещь",
    "parte": "часть",
    "deus": "бог",
    "estado": "государство",
    "forma": "форма",
    "caso": "случай",
    "tempo": "время",
    "tipo": "тип",
    "grupo": "группа",
    "lado": "сторона",
    "ponto": "точка",
    "nível": "уровень",
    "modo": "режим",
    "fim": "конец",
    "campo": "поле",
    "linha": "линия",
    "valor": "значение",
    "processo": "процесс",
    "resultado": "результат",
    "sistema": "система",
    "efeito": "эффект",
    "acordo": "соглашение",
    "direito": "право",
    "serviço": "услуга",
    "trabalho": "работа",
    "governo": "правительство",
    "empresa": "компания",
    "cidade": "город",
    "país": "страна",
    "mundo": "мир",
    "história": "история",
    "família": "семья",
    "problema": "проблема",
    "programa": "программа",
    "mercado": "рынок",
    "minuto": "минута",
    "noite": "ночь",
    "manhã": "утро",
    "guerra": "война",
    "festa": "праздник",
    "jogo": "игра",
    "corpo": "тело",
    "cabeça": "голова",
    "mão": "рука",
    "cara": "лицо",
    "porta": "дверь",
    "casa": "дом",
    "rua": "улица",
    "água": "вода",
    "terra": "земля",
    "mar": "море",
    "ar": "воздух",
    "fogo": "огонь",
    "amor": "любовь",
    "medo": "страх",
    "força": "сила",
    "lei": "закон",
    "voz": "голос",
    "imagem": "изображение",
    "nome": "имя",
    "número": "число",
    "preço": "цена",
    "dinheiro": "деньги",
    "música": "музыка",
    "filme": "фильм",
    "livro": "книга",
    "palavra": "слово",
    "pergunta": "вопрос",
    "resposta": "ответ",
    "fim-de-semana": "выходные",
    "fim de semana": "выходные",
    "dia": "день",
    "ano": "год",
}

NOUN_PACKS = {
    "pelo": ["волос", "форма", "случай", "вопрос", "система", "город"],
    "mesmo": ["то же самое", "вещь", "часть", "раз", "уровень", "время"],
    "tudo": ["всё", "часть", "вещь", "форма", "слово", "уровень"],
    "agora": ["настоящее время", "раз", "день", "год", "ночь", "время"],
    "era": ["эра", "режим", "форма", "поле", "процесс", "эффект"],
    "vez": ["раз", "случай", "форма", "уровень", "сторона", "пункт"],
    "coisa": ["вещь", "часть", "форма", "вопрос", "ответ", "слово"],
    "parte": ["часть", "случай", "форма", "система", "процесс", "результат"],
    "deus": ["бог", "мир", "закон", "страх", "любовь", "сила"],
    "estado": ["государство", "город", "страна", "рынок", "компания", "закон"],
    "forma": ["форма", "часть", "поле", "режим", "процесс", "результат"],
    "caso": ["случай", "часть", "вопрос", "ответ", "результат", "процесс"],
    "tempo": ["время", "день", "год", "ночь", "минута", "утро"],
    "tipo": ["тип", "режим", "уровень", "значение", "система", "процесс"],
    "grupo": ["группа", "семья", "компания", "рынок", "город", "страна"],
    "lado": ["сторона", "часть", "форма", "линия", "поле", "точка"],
    "ponto": ["точка", "линия", "поле", "значение", "уровень", "режим"],
    "nível": ["уровень", "значение", "режим", "система", "процесс", "результат"],
    "modo": ["режим", "уровень", "способ", "система", "процесс", "значение"],
    "fim": ["конец", "начало", "процесс", "результат", "день", "ночь"],
    "campo": ["поле", "линия", "точка", "уровень", "система", "процесс"],
    "linha": ["линия", "точка", "поле", "уровень", "значение", "режим"],
    "valor": ["значение", "уровень", "цена", "деньги", "результат", "система"],
    "processo": ["процесс", "результат", "система", "режим", "уровень", "форма"],
    "resultado": ["результат", "процесс", "эффект", "значение", "уровень", "система"],
    "sistema": ["система", "процесс", "режим", "уровень", "значение", "результат"],
    "efeito": ["эффект", "результат", "процесс", "система", "сила", "закон"],
    "acordo": ["соглашение", "закон", "право", "услуга", "процесс", "результат"],
    "direito": ["право", "закон", "соглашение", "услуга", "процесс", "результат"],
    "serviço": ["услуга", "работа", "процесс", "система", "результат", "рынок"],
    "trabalho": ["работа", "услуга", "процесс", "результат", "рынок", "компания"],
    "governo": ["правительство", "государство", "страна", "закон", "рынок", "компания"],
    "empresa": ["компания", "рынок", "услуга", "работа", "правительство", "город"],
    "cidade": ["город", "страна", "мир", "улица", "дом", "рынок"],
    "país": ["страна", "город", "мир", "правительство", "закон", "рынок"],
    "mundo": ["мир", "страна", "город", "история", "семья", "любовь"],
    "história": ["история", "мир", "страна", "семья", "проблема", "программа"],
    "família": ["семья", "история", "мир", "любовь", "страх", "сила"],
    "problema": ["проблема", "вопрос", "ответ", "результат", "процесс", "система"],
    "programa": ["программа", "система", "процесс", "результат", "режим", "значение"],
    "mercado": ["рынок", "компания", "цена", "деньги", "страна", "город"],
    "minuto": ["минута", "день", "год", "ночь", "утро", "время"],
    "noite": ["ночь", "утро", "день", "год", "время", "минута"],
    "manhã": ["утро", "ночь", "день", "год", "время", "минута"],
    "guerra": ["война", "страх", "сила", "закон", "государство", "мир"],
    "festa": ["праздник", "игра", "музыка", "фильм", "любовь", "ночь"],
    "jogo": ["игра", "фильм", "музыка", "книга", "вопрос", "ответ"],
    "corpo": ["тело", "голова", "рука", "лицо", "вода", "земля"],
    "cabeça": ["голова", "тело", "рука", "лицо", "дом", "дверь"],
    "mão": ["рука", "голова", "тело", "лицо", "дверь", "вода"],
    "cara": ["лицо", "голова", "тело", "рука", "имя", "голос"],
    "porta": ["дверь", "дом", "улица", "город", "вода", "огонь"],
    "casa": ["дом", "улица", "город", "страна", "дверь", "вода"],
    "rua": ["улица", "дом", "город", "страна", "дверь", "вода"],
    "água": ["вода", "земля", "море", "воздух", "огонь", "дом"],
    "terra": ["земля", "вода", "море", "воздух", "огонь", "страна"],
    "mar": ["море", "вода", "земля", "воздух", "огонь", "мир"],
    "ar": ["воздух", "вода", "земля", "море", "огонь", "мир"],
    "fogo": ["огонь", "вода", "земля", "море", "воздух", "страх"],
    "amor": ["любовь", "страх", "сила", "мир", "семья", "история"],
    "medo": ["страх", "любовь", "сила", "война", "закон", "мир"],
    "força": ["сила", "страх", "любовь", "закон", "война", "мир"],
    "lei": ["закон", "право", "государство", "правительство", "соглашение", "страна"],
    "voz": ["голос", "имя", "слово", "вопрос", "ответ", "музыка"],
    "imagem": ["изображение", "имя", "число", "слово", "фильм", "книга"],
    "nome": ["имя", "число", "слово", "вопрос", "ответ", "голос"],
    "número": ["число", "имя", "цена", "значение", "слово", "уровень"],
    "preço": ["цена", "деньги", "рынок", "компания", "число", "значение"],
    "dinheiro": ["деньги", "цена", "рынок", "компания", "страна", "город"],
    "música": ["музыка", "фильм", "книга", "игра", "слово", "голос"],
    "filme": ["фильм", "музыка", "книга", "игра", "изображение", "история"],
    "livro": ["книга", "фильм", "музыка", "слово", "история", "изображение"],
    "palavra": ["слово", "вопрос", "ответ", "имя", "голос", "книга"],
    "pergunta": ["вопрос", "ответ", "слово", "имя", "число", "голос"],
    "resposta": ["ответ", "вопрос", "слово", "результат", "процесс", "значение"],
    "dia": ["день", "год", "ночь", "утро", "минута", "время"],
    "ano": ["год", "день", "ночь", "утро", "минута", "время"],
}

def normalize(s: str) -> str:
    return " ".join((s or "").strip().lower().split())

def bad_gloss(gloss: str) -> bool:
    g = normalize(gloss)
    if g in BAD_EXACT:
        return True
    return any(x in g for x in BAD_SUBSTR)

def active_or_existing(conn: sqlite3.Connection, lemma: str, pos: str) -> bool:
    row = conn.execute(
        """
        SELECT 1
        FROM vocab_items
        WHERE lower(trim(lemma)) = ? AND pos = ?
        LIMIT 1
        """,
        (normalize(lemma), pos),
    ).fetchone()
    return row is not None

def table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    rows = conn.execute("PRAGMA table_info(%s)" % table).fetchall()
    return [str(r[1]) for r in rows]

def insert_item(conn: sqlite3.Connection, *, lemma: str, pos: str, freq_rank: int, ru_gloss: str, choices: list[str]) -> int:
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
            payload[col] = "Что значит это слово?\n\n" + lemma
        elif col == "correct_answer":
            payload[col] = ru_gloss
        elif col == "is_active":
            payload[col] = 1
        elif col == "source_type":
            payload[col] = "manual_review_high"
        elif col in ("created_at", "updated_at"):
            payload[col] = "__NOW__"

    cols = list(payload.keys())
    vals_sql = []
    args = []
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
                row_payload[col] = 1 if normalize(choice) == normalize(ru_gloss) else 0
            elif col == "position_index":
                row_payload[col] = idx
            elif col in ("created_at", "updated_at"):
                row_payload[col] = "__NOW__"

        cols2 = list(row_payload.keys())
        vals_sql2 = []
        args2 = []
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

def active_by_pos(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute(
        """
        SELECT pos, COUNT(*)
        FROM vocab_items
        WHERE is_active = 1
        GROUP BY pos
        ORDER BY pos
        """
    ).fetchall()
    return {str(r[0]): int(r[1]) for r in rows}

def build_candidates() -> list[dict]:
    rows = []
    with SRC.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            lemma = (r.get("lemma") or "").strip()
            pos = (r.get("pos") or "").strip()
            if pos != "noun":
                continue
            ru_gloss = MANUAL_RU.get(lemma, "").strip()
            if not ru_gloss:
                continue
            if bad_gloss(ru_gloss):
                continue
            choices = NOUN_PACKS.get(lemma)
            if not choices or len(choices) != 6 or len(set(choices)) != 6:
                continue
            if normalize(ru_gloss) != normalize(choices[0]):
                continue
            try:
                freq_rank = int((r.get("freq_rank") or "999999").strip())
            except Exception:
                freq_rank = 999999
            rows.append({
                "lemma": lemma,
                "pos": pos,
                "freq_rank": freq_rank,
                "ru_gloss": ru_gloss,
                "choices": choices,
                "source_file": r.get("source_file") or "",
            })
    rows.sort(key=lambda x: (x["freq_rank"], x["lemma"]))
    return rows

def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["dryrun", "apply"], required=True)
    ap.add_argument("--limit", type=int, default=60)
    args = ap.parse_args()

    outdir = ART / ("noun_factory_v1_" + args.mode + "_" + time.strftime("%Y%m%d_%H%M%S"))
    outdir.mkdir(parents=True, exist_ok=True)

    candidates = build_candidates()
    conn = sqlite3.connect(DB)
    try:
        before = active_by_pos(conn)
        selected = []
        skipped_existing = []
        for row in candidates:
            if len(selected) >= args.limit:
                break
            if active_or_existing(conn, row["lemma"], "noun"):
                skipped_existing.append(row["lemma"])
                continue
            selected.append(row)

        inserted = []
        if args.mode == "apply":
            for row in selected:
                item_id = insert_item(
                    conn,
                    lemma=row["lemma"],
                    pos="noun",
                    freq_rank=row["freq_rank"],
                    ru_gloss=row["ru_gloss"],
                    choices=row["choices"],
                )
                inserted.append({
                    "id": item_id,
                    "lemma": row["lemma"],
                    "correct_answer": row["ru_gloss"],
                    "freq_rank": row["freq_rank"],
                })
            conn.commit()

        after = active_by_pos(conn)
        report = {
            "mode": args.mode,
            "limit": args.limit,
            "candidate_total": len(candidates),
            "selected_total": len(selected),
            "skipped_existing_total": len(skipped_existing),
            "before_active_by_pos": before,
            "after_active_by_pos": after,
            "structural_status_after": structural_status(conn),
            "selected_preview": selected[:25],
            "inserted_total": len(inserted),
            "inserted": inserted,
        }
    finally:
        conn.close()

    (outdir / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(outdir / "summary.json")

if __name__ == "__main__":
    main()
