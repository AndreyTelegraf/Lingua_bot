from __future__ import annotations
import csv
import json
import re
import sqlite3
from collections import Counter
from datetime import datetime, UTC
from pathlib import Path

BASE = Path("/home/andrey/Projects/lingua_bot_v2")
DB = BASE / "data" / "lingua_staging.db"
TS = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
OUT_DIR = BASE / "artifacts" / f"weak_distractor_cases_{TS}"

def normalize(s: str) -> str:
    return " ".join((s or "").strip().lower().split())

BIN_ORDER = {"1K":1,"2K":2,"5K":3,"10K":4,"20K":5}

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    items = conn.execute("""
        SELECT id,lemma,correct_answer,pos,bin_name,level,freq_rank
        FROM vocab_items
        WHERE is_active=1
    """).fetchall()

    # build lookup table of answers
    answer_meta={}
    for r in conn.execute("SELECT correct_answer,bin_name,pos FROM vocab_items WHERE is_active=1"):
        answer_meta[normalize(r["correct_answer"])] = (r["bin_name"], r["pos"])

    rows=[]
    flag_counter=Counter()

    for item in items:

        choices=conn.execute("""
            SELECT choice_text,is_correct
            FROM vocab_choices
            WHERE item_id=?
        """,(item["id"],)).fetchall()

        choice_texts=[str(r["choice_text"] or "") for r in choices]
        distractors=[str(r["choice_text"] or "") for r in choices if int(r["is_correct"] or 0)!=1]

        flags=[]
        notes=[]

        if len(choice_texts)!=6:
            flags.append("BAD_CHOICE_COUNT")

        if len(set(choice_texts))!=len(choice_texts):
            flags.append("DUPLICATE_CHOICES")

        if sum(int(r["is_correct"] or 0) for r in choices)!=1:
            flags.append("BAD_CORRECT_COUNT")

        # meta check
        matched_meta=0
        pos_mismatch=0
        item_bin_rank=BIN_ORDER.get(item["bin_name"],99)

        for d in distractors:
            meta=answer_meta.get(normalize(d))
            if meta:
                matched_meta+=1
                b2=BIN_ORDER.get(meta[0],99)
                if meta[1]!=item["pos"]:
                    pos_mismatch+=1

        if matched_meta<=2:
            flags.append("LOW_META_MATCH")

        if pos_mismatch>=4:
            flags.append("HEAVY_POS_MISMATCH")

        triage="PASS"
        if any(f in flags for f in ["BAD_CHOICE_COUNT","DUPLICATE_CHOICES","BAD_CORRECT_COUNT"]):
            triage="REBUILD"
        elif flags:
            triage="REVIEW"

        for f in flags:
            flag_counter[f]+=1

        rows.append({
            "id":item["id"],
            "lemma":item["lemma"],
            "correct_answer":item["correct_answer"],
            "pos":item["pos"],
            "bin_name":item["bin_name"],
            "choices":" | ".join(choice_texts),
            "flags":";".join(flags),
            "triage":triage
        })

    full=OUT_DIR/"weak_distractor_cases_full.csv"

    with full.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    summary={
        "items":len(rows),
        "flag_counts":dict(flag_counter),
        "out_dir":str(OUT_DIR)
    }

    print(json.dumps(summary,ensure_ascii=False,indent=2))
    conn.close()

if __name__=="__main__":
    main()
