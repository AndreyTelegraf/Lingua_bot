from __future__ import annotations

import json
import shutil
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import re

ROOT = Path("/home/andrey/Projects/lingua_bot_v2")
DB_PATH = ROOT / "data/lingua_staging.db"
CANDIDATES_PATH = ROOT / "data/community_quality/community_quality_rewrite_candidates_v2.json"
OUT_DIR = ROOT / "data/community_quality"
BACKUP_DIR = OUT_DIR / "backups"
SUMMARY_PATH = OUT_DIR / "community_quality_rewrite_apply_v1_summary.json"

TABLE = "community_content_items"
TEXT_COL = "text"
ACTIVE_COL = "is_active"
UPDATED_COL = "updated_at"

LIMIT = 8

TARGET_IDS = [7, 10, 13, 336, 342, 338, 345, 347]

OLD_NEW = {
    7: (
        "Как по-человечески уточнить у senhorio, входит ли internet или это опять квест на выживание?",
        "Что обычно говорят, когда нужно уточнить у senhorio, входит ли internet или это опять квест на выживание?",
    ),
    10: (
        "Как мягко намекнуть продавцу, что preço fixo звучит смело, но рынок видит это иначе?",
        "Какими словами лучше намекнуть продавцу, что preço fixo звучит смело, но рынок видит это иначе?",
    ),
    13: (
        "Как сказать в аптеке, что нужно что-то от горла, но без ощущения, что читаешь диссертацию?",
        "Что обычно говорят в аптеке, когда нужно что-то от горла, но без ощущения, что читаешь диссертацию?",
    ),
    336: (
        "Как здесь правильно спросить, если сотрудник намекает, что чего-то не хватает, и нужно быстро понять, какого документа не достаёт, чтобы это звучало естественно и по-живому?",
        "Что обычно спрашивают здесь, когда сотрудник намекает, что чего-то не хватает, и нужно быстро понять, какого документа не достаёт, чтобы это звучало естественно и по-живому?",
    ),
    342: (
        "Как в разговоре обычно скажут, если цена на кассе не совпала с ценником, и нужно спокойно это уточнить, чтобы это звучало естественно и по-живому?",
        "Что обычно говорят в такой ситуации, когда цена на кассе не совпала с ценником, и нужно спокойно это уточнить, чтобы это звучало естественно и по-живому?",
    ),
    338: (
        "Что обычно говорят, когда после жалобы на поломку нужно вежливо напомнить хозяину квартиры и уточнить, когда ждать мастера, если хочется сказать естественно, а не как по учебнику?",
        "Что обычно говорят, когда после жалобы на поломку нужно вежливо напомнить хозяину квартиры и уточнить, когда ждать мастера?",
    ),
    345: (
        "Что обычно спрашивают, когда из-за сбоя непонятно, куда идти дальше, и нужно быстро переспросить следующий шаг, если цель — выяснить, что делать дальше, чтобы это звучало живо и по-местному?",
        "Что обычно спрашивают, когда из-за сбоя непонятно, куда идти дальше, и нужно быстро переспросить следующий шаг?",
    ),
    347: (
        "Какими словами лучше сказать, когда после первой вежливой просьбы шум продолжается, и нужно написать уже чуть твёрже, но без скандала?",
        "Какими словами лучше сказать, когда после первой вежливой просьбы шум продолжается, и нужно написать уже чуть твёрже, но без скандала?",
    ),
}

def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

def tokenize(text: str) -> list[str]:
    return re.findall(r"[^\W_]+", text.lower(), flags=re.UNICODE)

def audit(conn: sqlite3.Connection) -> dict:
    rows = conn.execute(
        f"SELECT id, {TEXT_COL} FROM {TABLE} WHERE {ACTIVE_COL}=1 ORDER BY id"
    ).fetchall()

    first1 = Counter()
    first2 = Counter()
    first3 = Counter()

    for _id, text in rows:
        toks = tokenize(text or "")
        if len(toks) >= 1:
            first1[" ".join(toks[:1])] += 1
        if len(toks) >= 2:
            first2[" ".join(toks[:2])] += 1
        if len(toks) >= 3:
            first3[" ".join(toks[:3])] += 1

    return {
        "active_count": len(rows),
        "top_first1": first1.most_common(20),
        "top_first2": first2.most_common(20),
        "top_first3": first3.most_common(20),
    }

def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    if not DB_PATH.exists():
        raise SystemExit(f"DB not found: {DB_PATH}")
    if not CANDIDATES_PATH.exists():
        raise SystemExit(f"Candidates file not found: {CANDIDATES_PATH}")

    backup_path = BACKUP_DIR / f"lingua_staging_before_community_quality_rewrite_apply_v1_{now_utc()}.db"
    shutil.copy2(DB_PATH, backup_path)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    before = audit(conn)

    selected_ids = TARGET_IDS[:LIMIT]
    applied = []
    mismatched = []
    missing = []

    conn.execute("BEGIN")
    try:
        for item_id in selected_ids:
            old_text, new_text = OLD_NEW[item_id]
            row = conn.execute(
                f"SELECT id, {TEXT_COL} FROM {TABLE} WHERE id = ?",
                (item_id,),
            ).fetchone()

            if row is None:
                missing.append({"id": item_id, "reason": "row_not_found"})
                continue

            current_text = (row[TEXT_COL] or "").strip()
            if current_text != old_text.strip():
                mismatched.append({
                    "id": item_id,
                    "expected_old": old_text,
                    "current": current_text,
                })
                continue

            conn.execute(
                f"""
                UPDATE {TABLE}
                SET {TEXT_COL} = ?, {UPDATED_COL} = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (new_text, item_id),
            )
            applied.append({
                "id": item_id,
                "old": old_text,
                "new": new_text,
            })

        if len(applied) < 6:
            raise RuntimeError(f"Applied only {len(applied)} rewrites; expected at least 6")

        conn.commit()
    except Exception:
        conn.rollback()
        conn.close()
        raise

    after = audit(conn)

    control_rows = conn.execute(
        f"SELECT id, {TEXT_COL} FROM {TABLE} WHERE id IN ({','.join(str(x) for x in selected_ids)}) ORDER BY id"
    ).fetchall()
    conn.close()

    summary = {
        "status": "ok",
        "db_path": str(DB_PATH),
        "backup_path": str(backup_path),
        "table": TABLE,
        "text_col": TEXT_COL,
        "selected_ids": selected_ids,
        "applied_count": len(applied),
        "missing_count": len(missing),
        "mismatched_count": len(mismatched),
        "applied": applied,
        "missing": missing,
        "mismatched": mismatched,
        "before_audit": before,
        "after_audit": after,
        "control_rows_after": [{"id": int(r["id"]), "text": r[TEXT_COL]} for r in control_rows],
    }

    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
