import sqlite3
from pathlib import Path

from services.vocab_qa.adverb_gloss_audit import run_adverb_audit

def test_run_adverb_audit(tmp_path: Path):
    db = tmp_path / "t.db"
    conn = sqlite3.connect(db)
    conn.executescript("""
    create table vocab_items (
      id integer primary key,
      lemma text,
      question_text text,
      correct_answer text,
      difficulty_band text,
      lexical_band text,
      pos text,
      topic_tag text,
      is_active integer,
      created_at text,
      updated_at text,
      freq_rank integer,
      level text,
      bin_name text,
      cefr_estimate text,
      concept_group text
    );
    create table vocab_choices (
      id integer primary key,
      item_id integer,
      choice_text text,
      is_correct integer,
      position_index integer,
      created_at text
    );
    """)
    conn.execute("""
        insert into vocab_items
        (id, lemma, question_text, correct_answer, difficulty_band, lexical_band, pos, topic_tag, is_active, created_at, updated_at, freq_rank, level, bin_name, cefr_estimate, concept_group)
        values
        (1, 'cedo', 'cedo', 'седо', null, null, 'adverb', null, 1, '', '', null, null, null, null, null)
    """)
    vals = ["седо","рано","поздно","возможно","быстро","медленно"]
    for i, txt in enumerate(vals, start=1):
        conn.execute(
            "insert into vocab_choices(id,item_id,choice_text,is_correct,position_index,created_at) values (?,?,?,?,?,?)",
            (i, 1, txt, 1 if i == 1 else 0, i - 1, ""),
        )
    conn.commit()
    conn.close()

    summary = run_adverb_audit(str(db), str(tmp_path))
    assert summary["active_items_scanned"] == 1
    assert summary["reject_count"] == 1
