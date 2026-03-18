import csv
import sqlite3
import subprocess
import sys
from pathlib import Path


def test_apply_auto_rejects(tmp_path: Path):
    db = tmp_path / "t.db"
    conn = sqlite3.connect(db)
    conn.executescript("""
    create table vocab_items (
      id integer primary key,
      lemma text,
      pos text,
      is_active integer
    );
    create table vocab_choices (
      id integer primary key,
      item_id integer,
      choice_text text,
      is_correct integer
    );
    """)
    conn.execute("insert into vocab_items values (1, 'durante', 'noun', 1)")
    for i, txt in enumerate(["дюрант","дом","стол","кот","река","лес"], start=1):
        conn.execute(
            "insert into vocab_choices(id,item_id,choice_text,is_correct) values (?,?,?,?)",
            (i, 1, txt, 1 if i == 1 else 0),
        )
    conn.commit()
    conn.close()

    art = tmp_path
    with (art / "noun_ru_gloss_reject_auto.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[
            "id","lemma","pos","correct_answer","status","risk_score",
            "flags","normalized_correct_answer","suggested_action","explanation"
        ])
        w.writeheader()
        w.writerow({
            "id": 1,
            "lemma": "durante",
            "pos": "noun",
            "correct_answer": "дюрант",
            "status": "reject",
            "risk_score": 100,
            "flags": "translit_like_ru|lemma_phonetic_copy",
            "normalized_correct_answer": "дюрант",
            "suggested_action": "deactivate",
            "explanation": "x",
        })

    with (art / "noun_ru_gloss_review.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id"])

    subprocess.run(
        [
            sys.executable,
            "tools/apply_noun_ru_gloss_decisions.py",
            "--db", str(db),
            "--artifacts-dir", str(art),
            "--apply-auto-rejects",
        ],
        check=True,
    )

    conn = sqlite3.connect(db)
    row = conn.execute("select is_active from vocab_items where id=1").fetchone()
    conn.close()
    assert row[0] == 0
