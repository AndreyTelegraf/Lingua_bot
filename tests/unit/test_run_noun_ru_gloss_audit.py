import sqlite3
from pathlib import Path

from services.vocab_qa.ru_gloss_audit import run_noun_audit


def test_run_noun_audit(tmp_path: Path):
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

    summary = run_noun_audit(str(db), str(tmp_path))
    assert summary["active_items_scanned"] == 1
    assert summary["reject_count"] == 1
    assert (tmp_path / "noun_ru_gloss_audit.jsonl").exists()
    assert (tmp_path / "noun_ru_gloss_review.csv").exists()
    assert (tmp_path / "noun_ru_gloss_reject_auto.csv").exists()
