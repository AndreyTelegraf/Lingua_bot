#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import re
import shutil
import sqlite3
from datetime import datetime, UTC
from pathlib import Path

DB_PATH = Path("data/lingua_staging.db")
BACKUP_DIR = Path("tmp/db_backups")
REPORT_PATH = Path("tmp/cleanup_2k_adjectives_zero_choice_dups_report.json")
AUDIT_DIR = Path("tmp/2k_adjectives_priority_audit")
AUDIT_CSV = AUDIT_DIR / "staging_2k_adjectives_priority_audit.csv"
AUDIT_JSON = AUDIT_DIR / "staging_2k_adjectives_priority_audit.json"

PROPER_NAME_LEMMAS = {
    "roberto","marcos","daniel","ricardo","eduardo","fernando","jorge",
    "israel","itália","alemanha","argentina","índia","rússia","frança",
    "méxico","japão","áfrica","espanha","paris","lima","máximo",
}
SUSPECT_TRANSLATIONS = {
    "коробка передач","осада","подача","брутальность","воссоединение",
    "помилование","изъян","шкура","доблесть","набла","ru","блядь","негр",
    "кни́га чи́сел","нача́ло","рефо́рма","pаспределение",
}
NON_NOUNISH_TRANSLATIONS = {
    "русский","плохой","левый","вице",
}
OBSCENE_OR_SLUR = {"блядь","негр"}

def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

def row_to_dict(row: sqlite3.Row) -> dict:
    return {k: row[k] for k in row.keys()}

def fetch_adjective_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT
          vi.id,
          vi.lemma,
          vi.correct_answer,
          vi.pos,
          vi.bin_name,
          vi.freq_rank,
          vi.is_active,
          vi.topic_tag,
          SUM(CASE WHEN vc.id IS NOT NULL THEN 1 ELSE 0 END) AS choice_count,
          SUM(CASE WHEN COALESCE(vc.is_correct,0)=1 THEN 1 ELSE 0 END) AS correct_count
        FROM vocab_items vi
        LEFT JOIN vocab_choices vc ON vc.item_id = vi.id
        WHERE vi.pos = 'adjective'
          AND vi.bin_name = '2K'
        GROUP BY
          vi.id, vi.lemma, vi.correct_answer, vi.pos, vi.bin_name,
          vi.freq_rank, vi.is_active, vi.topic_tag
        ORDER BY vi.freq_rank DESC, vi.lemma ASC, vi.id ASC
        """
    ).fetchall()

def get_choices_joined(conn: sqlite3.Connection, item_id: int) -> str:
    rows = conn.execute(
        """
        SELECT choice_text, is_correct, position_index
        FROM vocab_choices
        WHERE item_id = ?
        ORDER BY position_index ASC, id ASC
        """,
        (item_id,),
    ).fetchall()
    return " | ".join(
        f"{'*' if int(r['is_correct'] or 0) == 1 else '-'} {r['choice_text']}"
        for r in rows
    )

def collect_duplicate_groups(conn: sqlite3.Connection) -> list[dict]:
    dup_keys = conn.execute(
        """
        SELECT LOWER(TRIM(lemma)) AS lemma_key, COUNT(*) AS n
        FROM vocab_items
        WHERE pos = 'adjective' AND bin_name = '2K'
        GROUP BY LOWER(TRIM(lemma))
        HAVING COUNT(*) > 1
        ORDER BY lemma_key
        """
    ).fetchall()

    groups = []
    for dk in dup_keys:
        lemma_key = dk["lemma_key"]
        rows = conn.execute(
            """
            SELECT
              vi.id,
              vi.lemma,
              vi.correct_answer,
              vi.freq_rank,
              vi.is_active,
              vi.topic_tag,
              SUM(CASE WHEN vc.id IS NOT NULL THEN 1 ELSE 0 END) AS choice_count,
              SUM(CASE WHEN COALESCE(vc.is_correct,0)=1 THEN 1 ELSE 0 END) AS correct_count
            FROM vocab_items vi
            LEFT JOIN vocab_choices vc ON vc.item_id = vi.id
            WHERE vi.pos = 'adjective'
              AND vi.bin_name = '2K'
              AND LOWER(TRIM(vi.lemma)) = ?
            GROUP BY vi.id, vi.lemma, vi.correct_answer, vi.freq_rank, vi.is_active, vi.topic_tag
            ORDER BY vi.is_active DESC, choice_count DESC, vi.id ASC
            """,
            (lemma_key,),
        ).fetchall()
        groups.append({
            "lemma_key": lemma_key,
            "rows": [row_to_dict(r) for r in rows],
        })
    return groups

def classify_issue(row: sqlite3.Row | dict, choices_joined: str) -> str:
    lemma = str(row["lemma"]).strip().lower()
    ans = str(row["correct_answer"]).strip().lower()
    tags: list[str] = []

    if lemma in PROPER_NAME_LEMMAS:
        tags.append("PROPER_NAME_OR_COUNTRY")

    if ans in SUSPECT_TRANSLATIONS:
        tags.append("SUSPECT_TRANSLATION")

    if ans in NON_NOUNISH_TRANSLATIONS:
        tags.append("NON_NOUNISH_TRANSLATION")

    if ans in OBSCENE_OR_SLUR:
        tags.append("OBSCENE_OR_SLUR")

    if re.search(r"[a-zA-Z]", ans) and not re.fullmatch(r"[a-zA-Z\s\-]+", ans):
        tags.append("MIXED_SCRIPT")
    elif ans in {"ru", "pаспределение"}:
        tags.append("BROKEN_ENCODING_OR_TRANSLIT")

    if str(row["choice_count"]) == "0":
        tags.append("ZERO_CHOICE")

    if " * " not in f" {choices_joined} " and choices_joined:
        tags.append("BROKEN_CHOICES")

    return "|".join(tags)

def main() -> None:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    backup_path = BACKUP_DIR / f"lingua_staging_before_cleanup_2k_adjectives_zero_choice_dups_{utc_stamp()}.db"
    shutil.copy2(DB_PATH, backup_path)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    before_groups = collect_duplicate_groups(conn)

    delete_ids: list[int] = []
    deleted_rows: list[dict] = []

    for grp in before_groups:
        rows = grp["rows"]
        has_keeper = any(
            int(r["is_active"] or 0) == 1 or int(r["choice_count"] or 0) > 0
            for r in rows
        )
        if not has_keeper:
            continue
        for r in rows:
            if int(r["is_active"] or 0) == 0 and int(r["choice_count"] or 0) == 0:
                delete_ids.append(int(r["id"]))
                deleted_rows.append({
                    "id": int(r["id"]),
                    "lemma": r["lemma"],
                    "correct_answer": r["correct_answer"],
                    "freq_rank": r["freq_rank"],
                    "is_active": r["is_active"],
                    "topic_tag": r["topic_tag"],
                })

    if delete_ids:
        conn.executemany("DELETE FROM vocab_choices WHERE item_id = ?", [(x,) for x in delete_ids])
        conn.executemany("DELETE FROM vocab_items WHERE id = ?", [(x,) for x in delete_ids])
        conn.commit()

    after_groups = collect_duplicate_groups(conn)

    adjective_rows = fetch_adjective_rows(conn)
    audit_rows: list[dict] = []
    for r in adjective_rows:
        if int(r["is_active"] or 0) != 1:
            continue
        cj = get_choices_joined(conn, int(r["id"]))
        issue_tags = classify_issue(r, cj)
        if issue_tags:
            audit_rows.append({
                "id": int(r["id"]),
                "lemma": str(r["lemma"]),
                "correct_answer": str(r["correct_answer"]),
                "pos": str(r["pos"]),
                "bin_name": str(r["bin_name"]),
                "freq_rank": int(r["freq_rank"]) if r["freq_rank"] is not None else None,
                "is_active": int(r["is_active"] or 0),
                "choice_count": int(r["choice_count"] or 0),
                "correct_count": int(r["correct_count"] or 0),
                "topic_tag": str(r["topic_tag"]) if r["topic_tag"] is not None else "",
                "issue_tags": issue_tags,
                "choices_joined": cj,
            })

    summary = {
        "db_path": str(DB_PATH),
        "backup_path": str(backup_path),
        "before_total_rows": len(fetch_adjective_rows(sqlite3.connect(DB_PATH))),
        "deleted_zero_choice_inactive_duplicate_ids": delete_ids,
        "deleted_zero_choice_inactive_duplicate_count": len(delete_ids),
        "remaining_duplicate_group_count": len(after_groups),
        "active_priority_audit_rows": len(audit_rows),
        "audit_csv": str(AUDIT_CSV),
        "audit_json": str(AUDIT_JSON),
        "report_path": str(REPORT_PATH),
    }

    with AUDIT_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "id","lemma","correct_answer","pos","bin_name","freq_rank","is_active",
                "choice_count","correct_count","topic_tag","issue_tags","choices_joined",
            ],
        )
        writer.writeheader()
        writer.writerows(audit_rows)

    AUDIT_JSON.write_text(
        json.dumps({"summary": summary, "rows": audit_rows}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    REPORT_PATH.write_text(
        json.dumps({
            "db_path": str(DB_PATH),
            "backup_path": str(backup_path),
            "before_duplicate_groups": before_groups,
            "deleted_zero_choice_inactive_duplicate_ids": delete_ids,
            "deleted_zero_choice_inactive_duplicate_count": len(delete_ids),
            "deleted_rows": deleted_rows,
            "after_duplicate_groups": after_groups,
            "after_duplicate_group_count": len(after_groups),
            "active_priority_audit_rows": len(audit_rows),
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("===== CLEANUP 2K ADJECTIVES ZERO-CHOICE DUPS =====")
    print(json.dumps({
        "db_path": str(DB_PATH),
        "backup_path": str(backup_path),
        "deleted_zero_choice_inactive_duplicate_count": len(delete_ids),
        "remaining_duplicate_group_count": len(after_groups),
        "active_priority_audit_rows": len(audit_rows),
        "report_path": str(REPORT_PATH),
        "audit_csv": str(AUDIT_CSV),
        "audit_json": str(AUDIT_JSON),
    }, ensure_ascii=False, indent=2))

    print("\n===== ACTIVE PRIORITY AUDIT ROWS =====")
    for row in audit_rows[:200]:
        print(json.dumps(row, ensure_ascii=False))

    conn.close()

if __name__ == "__main__":
    main()
