from __future__ import annotations

import sqlite3
import tempfile
import shutil
from pathlib import Path

import sys, os
BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from services.vocab_runtime.selector import get_next_item
from services.vocab_runtime.renderer import build_question_payload
from tools.vocab_v3.import_authoring_csv import main as import_main

BASE_DB = Path("data/lingua_staging.db")

def run():
    tmp_db = Path(tempfile.mkstemp(suffix=".db")[1])
    shutil.copy(BASE_DB, tmp_db)

    csv_path = Path(tempfile.mkstemp(suffix=".csv")[1])
    csv_path.write_text(
        "lemma,pos,bin_name,prompt,correct_choice,distractor_1,distractor_2,distractor_3,distractor_4,distractor_5,source_note,author_note,audit_status,audit_reasons\n"
        "cão,noun,1K,Что значит это слово? cão,собака,кошка,дом,машина,река,еда,manual,ok,certified,ok\n"
        "comer,verb,1K,Что значит это слово? comer,есть,спать,читать,писать,бежать,прыгать,manual,ok,certified,ok\n"
        "rápido,adjective,1K,Что значит это слово? rápido,быстрый,медленный,тяжёлый,грустный,яркий,тихий,manual,ok,certified,ok\n"
        "ontem,adverb,1K,Что значит это слово? ontem,вчера,сегодня,завтра,редко,часто,сейчас,manual,ok,certified,ok\n",
        encoding="utf-8"
    )

    import sys
    sys.argv = ["import", "--db", str(tmp_db), str(csv_path)]
    import_main()

    conn = sqlite3.connect(tmp_db)
    conn.row_factory = sqlite3.Row

    conn.execute("INSERT INTO users (telegram_user_id) VALUES (999999401)")
    user_id = conn.execute("SELECT id FROM users WHERE telegram_user_id=999999401").fetchone()[0]

    conn.execute("INSERT INTO mode_runs (user_id, mode, status) VALUES (?, 'vocab', 'in_progress')", (user_id,))
    mode_run_id = conn.execute("SELECT id FROM mode_runs WHERE user_id=?", (user_id,)).fetchone()[0]

    conn.execute("""
    INSERT INTO vocab_attempts (user_id, mode_run_id, question_limit, status)
    VALUES (?, ?, 24, 'in_progress')
    """, (user_id, mode_run_id))
    attempt_id = conn.execute("SELECT id FROM vocab_attempts WHERE user_id=?", (user_id,)).fetchone()[0]

    item = get_next_item(conn, attempt_id=attempt_id)
    if item is None:
        raise SystemExit("FAIL: selector returned None")

    payload = build_question_payload(conn, item_id=item["id"], attempt_id=attempt_id)
    if len(payload["choices"]) != 6:
        raise SystemExit("FAIL: invalid choices")

    print("PASS_V3_SMOKE_RUNTIME item_id=", item["id"])

    conn.close()
    tmp_db.unlink(missing_ok=True)
    csv_path.unlink(missing_ok=True)

if __name__ == "__main__":
    run()
