from __future__ import annotations

import csv
import json
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime, UTC
from pathlib import Path
from typing import Any


DB_PATH = Path("data/lingua_staging.db")
TMP_DIR = Path("tmp")
BACKUP_DIR = TMP_DIR / "db_backups"
REPORT_DIR = TMP_DIR / "bank_pipeline_reports"
CANONICAL_PATH = Path("data/bank_canonical_translations.json")


@dataclass(slots=True)
class LayerSpec:
    pos: str
    bin_name: str


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def layer_slug(spec: LayerSpec) -> str:
    return f"{spec.bin_name.lower()}_{spec.pos}s"


def review_dir(spec: LayerSpec) -> Path:
    return TMP_DIR / f"{layer_slug(spec)}_review"


def review_csv_path(spec: LayerSpec) -> Path:
    return review_dir(spec) / f"staging_{layer_slug(spec)}_review.csv"


def review_json_path(spec: LayerSpec) -> Path:
    return review_dir(spec) / f"staging_{layer_slug(spec)}_review.json"


def audit_dir(spec: LayerSpec) -> Path:
    return TMP_DIR / f"{layer_slug(spec)}_priority_audit"


def audit_csv_path(spec: LayerSpec) -> Path:
    return audit_dir(spec) / f"staging_{layer_slug(spec)}_priority_audit.csv"


def audit_json_path(spec: LayerSpec) -> Path:
    return audit_dir(spec) / f"staging_{layer_slug(spec)}_priority_audit.json"


def manifest_path(spec: LayerSpec) -> Path:
    return REPORT_DIR / f"{spec.pos}_{spec.bin_name}_{utc_stamp()}.json"


def ensure_dirs(spec: LayerSpec) -> None:
    review_dir(spec).mkdir(parents=True, exist_ok=True)
    audit_dir(spec).mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)


def connect_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def backup_db(label: str) -> str:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    dst = BACKUP_DIR / f"lingua_staging_before_{label}_{utc_stamp()}.db"
    shutil.copy2(DB_PATH, dst)
    return str(dst)


def load_canonical_registry() -> dict[str, Any]:
    if not CANONICAL_PATH.exists():
        return {}
    return json.loads(CANONICAL_PATH.read_text(encoding="utf-8"))


def fetch_choices(conn: sqlite3.Connection, item_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT id, choice_text, is_correct, position_index
        FROM vocab_choices
        WHERE item_id = ?
        ORDER BY position_index ASC, id ASC
        """,
        (item_id,),
    ).fetchall()


def fetch_choices_joined(conn: sqlite3.Connection, item_id: int) -> str:
    rows = fetch_choices(conn, item_id)
    return " | ".join(
        f"{'*' if int(r['is_correct']) == 1 else '-'} {r['choice_text']}" for r in rows
    )


def fetch_layer_rows(conn: sqlite3.Connection, spec: LayerSpec) -> list[sqlite3.Row]:
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
          COALESCE(COUNT(vc.id), 0) AS choice_count,
          COALESCE(SUM(CASE WHEN COALESCE(vc.is_correct, 0) = 1 THEN 1 ELSE 0 END), 0) AS correct_count
        FROM vocab_items vi
        LEFT JOIN vocab_choices vc ON vc.item_id = vi.id
        WHERE vi.pos = ?
          AND vi.bin_name = ?
        GROUP BY
          vi.id, vi.lemma, vi.correct_answer, vi.pos, vi.bin_name,
          vi.freq_rank, vi.is_active, vi.topic_tag
        ORDER BY vi.freq_rank DESC, vi.lemma ASC, vi.id ASC
        """,
        (spec.pos, spec.bin_name),
    ).fetchall()


def duplicate_groups(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        key = r["lemma"]
        buckets.setdefault(key, []).append(
            {
                "id": r["id"],
                "lemma": r["lemma"],
                "correct_answer": r["correct_answer"],
                "freq_rank": r["freq_rank"],
                "is_active": r["is_active"],
                "topic_tag": r["topic_tag"],
                "choice_count": r["choice_count"],
                "correct_count": r["correct_count"],
            }
        )
    return [{"lemma_key": k, "rows": v} for k, v in sorted(buckets.items()) if len(v) > 1]


def structural_issue_tags(conn: sqlite3.Connection, row: sqlite3.Row) -> list[str]:
    tags: list[str] = []
    choices = fetch_choices(conn, row["id"])
    texts = [c["choice_text"] for c in choices]
    correct_texts = [c["choice_text"] for c in choices if int(c["is_correct"]) == 1]
    distractor_texts = [c["choice_text"] for c in choices if int(c["is_correct"]) == 0]

    if int(row["is_active"]) == 1 and int(row["choice_count"]) != 6:
        tags.append("ACTIVE_BAD_CHOICE_COUNT")
    if int(row["is_active"]) == 1 and int(row["correct_count"]) != 1:
        tags.append("ACTIVE_BAD_CORRECT_COUNT")
    if len(texts) != len(set(texts)):
        tags.append("DUPLICATE_ANSWER_TEXTS")
    if correct_texts and any(t in distractor_texts for t in correct_texts):
        tags.append("CORRECT_DUPLICATED_IN_DISTRACTORS")

    registry = load_canonical_registry()
    canon_key = f"{row['lemma']}|{row['pos']}"
    canon = registry.get(canon_key)
    if canon:
        forbidden = set(canon.get("forbidden_ru_variants", []))
        allowed = set(canon.get("allowed_ru_variants", []))
        canonical_ru = canon.get("canonical_ru")
        if row["correct_answer"] in forbidden:
            tags.append("SUSPECT_TRANSLATION")
        elif canonical_ru and row["correct_answer"] != canonical_ru and row["correct_answer"] not in allowed:
            tags.append("CANONICAL_MISMATCH")

    return tags


def build_review_pack(conn: sqlite3.Connection, spec: LayerSpec) -> dict[str, Any]:
    ensure_dirs(spec)
    rows = fetch_layer_rows(conn, spec)
    out_rows: list[dict[str, Any]] = []

    for r in rows:
        rec = dict(r)
        rec["choices_joined"] = fetch_choices_joined(conn, r["id"])
        out_rows.append(rec)

    csv_fields = [
        "id", "lemma", "correct_answer", "freq_rank", "is_active",
        "choice_count", "correct_count", "topic_tag", "choices_joined",
    ]
    with review_csv_path(spec).open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields)
        writer.writeheader()
        writer.writerows({k: row.get(k, "") for k in csv_fields} for row in out_rows)

    payload = {
        "summary": {
            "count": len(out_rows),
            "active_count": sum(1 for r in out_rows if int(r["is_active"]) == 1),
            "valid_6_1_count": sum(1 for r in out_rows if int(r["choice_count"]) == 6 and int(r["correct_count"]) == 1),
            "duplicates_count": len(duplicate_groups(rows)),
            "csv_path": str(review_csv_path(spec)),
            "json_path": str(review_json_path(spec)),
        },
        "rows": out_rows,
        "duplicates": duplicate_groups(rows),
    }
    review_json_path(spec).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload["summary"]


def build_priority_audit(conn: sqlite3.Connection, spec: LayerSpec) -> dict[str, Any]:
    ensure_dirs(spec)
    rows = fetch_layer_rows(conn, spec)
    audit_rows: list[dict[str, Any]] = []

    for r in rows:
        tags = structural_issue_tags(conn, r)
        if tags:
            rec = dict(r)
            rec["issue_tags"] = "|".join(tags)
            rec["choices_joined"] = fetch_choices_joined(conn, r["id"])
            audit_rows.append(rec)

    csv_fields = [
        "id", "lemma", "correct_answer", "pos", "bin_name", "freq_rank", "is_active",
        "choice_count", "correct_count", "topic_tag", "issue_tags", "choices_joined",
    ]
    with audit_csv_path(spec).open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields)
        writer.writeheader()
        writer.writerows({k: row.get(k, "") for k in csv_fields} for row in audit_rows)

    payload = {
        "summary": {
            "db_path": str(DB_PATH),
            "total_active_rows": sum(1 for r in rows if int(r["is_active"]) == 1),
            "audit_rows": len(audit_rows),
        },
        "rows": audit_rows,
    }
    audit_json_path(spec).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def cleanup_zero_choice_dups(conn: sqlite3.Connection, spec: LayerSpec, *, dry_run: bool) -> dict[str, Any]:
    rows = fetch_layer_rows(conn, spec)
    groups = duplicate_groups(rows)
    to_delete: list[int] = []

    for grp in groups:
        grp_rows = grp["rows"]
        has_usable = any(int(r["is_active"]) == 1 or int(r["choice_count"]) > 0 for r in grp_rows)
        if not has_usable:
            continue
        for r in grp_rows:
            if int(r["is_active"]) == 0 and int(r["choice_count"]) == 0:
                to_delete.append(int(r["id"]))

    if to_delete and not dry_run:
        q = ",".join("?" for _ in to_delete)
        conn.execute(f"DELETE FROM vocab_items WHERE id IN ({q})", to_delete)
        conn.commit()

    after_rows = fetch_layer_rows(conn, spec)
    return {
        "deleted_zero_choice_inactive_duplicates": len(to_delete),
        "deleted_ids": to_delete,
        "duplicate_groups_before": len(groups),
        "duplicate_groups_after": len(duplicate_groups(after_rows)),
    }


def purge_fully_inactive_dups(conn: sqlite3.Connection, spec: LayerSpec, *, dry_run: bool) -> dict[str, Any]:
    rows = fetch_layer_rows(conn, spec)
    groups = duplicate_groups(rows)
    to_delete: list[int] = []
    purged_groups = 0

    for grp in groups:
        grp_rows = grp["rows"]
        if all(int(r["is_active"]) == 0 for r in grp_rows):
            purged_groups += 1
            for r in grp_rows:
                to_delete.append(int(r["id"]))

    if to_delete and not dry_run:
        q = ",".join("?" for _ in to_delete)
        conn.execute(f"DELETE FROM vocab_items WHERE id IN ({q})", to_delete)
        conn.commit()

    return {
        "purged_fully_inactive_duplicate_group_count": purged_groups,
        "purged_fully_inactive_duplicate_item_count": len(to_delete),
        "purged_ids": to_delete,
    }


def apply_safe_semantic_fixes(conn: sqlite3.Connection, spec: LayerSpec, *, dry_run: bool) -> dict[str, Any]:
    registry = load_canonical_registry()
    rows = fetch_layer_rows(conn, spec)
    applied: list[dict[str, Any]] = []

    for r in rows:
        if int(r["is_active"]) != 1:
            continue
        canon_key = f"{r['lemma']}|{r['pos']}"
        canon = registry.get(canon_key)
        if not canon:
            continue
        canonical_ru = canon.get("canonical_ru")
        forbidden = set(canon.get("forbidden_ru_variants", []))
        if not canonical_ru or r["correct_answer"] not in forbidden:
            continue

        correct_rows = conn.execute(
            """
            SELECT id, choice_text
            FROM vocab_choices
            WHERE item_id = ? AND is_correct = 1
            ORDER BY position_index ASC, id ASC
            """,
            (r["id"],),
        ).fetchall()
        if len(correct_rows) != 1:
            continue

        applied.append(
            {
                "id": r["id"],
                "lemma": r["lemma"],
                "old_correct_answer": r["correct_answer"],
                "new_correct_answer": canonical_ru,
                "correct_choice_id": correct_rows[0]["id"],
            }
        )

        if not dry_run:
            conn.execute("UPDATE vocab_items SET correct_answer = ? WHERE id = ?", (canonical_ru, r["id"]))
            conn.execute("UPDATE vocab_choices SET choice_text = ? WHERE id = ?", (canonical_ru, correct_rows[0]["id"]))

    if applied and not dry_run:
        conn.commit()

    return {"semantic_updates": len(applied), "applied": applied}


def run_layer_pipeline(
    spec: LayerSpec,
    *,
    build_review_pack: bool,
    cleanup_zero_choice_dups: bool,
    build_priority_audit: bool,
    apply_safe_fixes: bool,
    purge_fully_inactive_dups: bool,
    dry_run: bool,
) -> dict[str, Any]:
    ensure_dirs(spec)
    conn = connect_db()
    try:
        before_rows = fetch_layer_rows(conn, spec)
        before_total_rows = len(before_rows)
        dup_before = len(duplicate_groups(before_rows))

        if any([cleanup_zero_choice_dups, purge_fully_inactive_dups, apply_safe_fixes]) and not dry_run:
            backup_db(f"bank_pipeline_{spec.pos}_{spec.bin_name}")

        if build_review_pack:
            build_review_pack_summary = build_review_pack_fn(conn, spec)
        else:
            build_review_pack_summary = None

        audit_before_fix = build_priority_audit_fn(conn, spec)["summary"]["audit_rows"] if build_priority_audit else 0

        cleanup_stats = {
            "deleted_zero_choice_inactive_duplicates": 0,
            "deleted_ids": [],
            "duplicate_groups_before": dup_before,
            "duplicate_groups_after": dup_before,
        }
        if cleanup_zero_choice_dups:
            cleanup_stats = cleanup_zero_choice_dups_fn(conn, spec, dry_run=dry_run)

        purge_stats = {
            "purged_fully_inactive_duplicate_group_count": 0,
            "purged_fully_inactive_duplicate_item_count": 0,
            "purged_ids": [],
        }
        if purge_fully_inactive_dups:
            purge_stats = purge_fully_inactive_dups_fn(conn, spec, dry_run=dry_run)

        if build_priority_audit:
            build_priority_audit_fn(conn, spec)

        semantic_stats = {"semantic_updates": 0, "applied": []}
        if apply_safe_fixes:
            semantic_stats = apply_safe_semantic_fixes_fn(conn, spec, dry_run=dry_run)

        audit_after_fix = build_priority_audit_fn(conn, spec)["summary"]["audit_rows"] if build_priority_audit else 0
        after_rows = fetch_layer_rows(conn, spec)

        metrics = {
            "pos": spec.pos,
            "bin_name": spec.bin_name,
            "before_total_rows": before_total_rows,
            "after_total_rows": len(after_rows),
            "active_rows": sum(1 for r in after_rows if int(r["is_active"]) == 1),
            "valid_6_1_rows": sum(1 for r in after_rows if int(r["choice_count"]) == 6 and int(r["correct_count"]) == 1),
            "duplicate_groups_before": dup_before,
            "duplicate_groups_after": len(duplicate_groups(after_rows)),
            "deleted_zero_choice_inactive_duplicates": cleanup_stats["deleted_zero_choice_inactive_duplicates"],
            "purged_fully_inactive_duplicate_group_count": purge_stats["purged_fully_inactive_duplicate_group_count"],
            "purged_fully_inactive_duplicate_item_count": purge_stats["purged_fully_inactive_duplicate_item_count"],
            "semantic_updates": semantic_stats["semantic_updates"],
            "audit_rows_before_fix": audit_before_fix,
            "audit_rows_after_fix": audit_after_fix,
            "final_status": "PASS" if audit_after_fix == 0 else "FAIL",
        }

        manifest = {
            "spec": {"pos": spec.pos, "bin_name": spec.bin_name},
            "dry_run": dry_run,
            "review_csv": str(review_csv_path(spec)),
            "review_json": str(review_json_path(spec)),
            "audit_csv": str(audit_csv_path(spec)),
            "audit_json": str(audit_json_path(spec)),
            "metrics": metrics,
            "cleanup_stats": cleanup_stats,
            "purge_stats": purge_stats,
            "semantic_stats": semantic_stats,
            "review_summary": build_review_pack_summary,
        }
        mpath = manifest_path(spec)
        manifest["manifest_path"] = str(mpath)
        mpath.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        return manifest
    finally:
        conn.close()


build_review_pack_fn = build_review_pack
build_priority_audit_fn = build_priority_audit
cleanup_zero_choice_dups_fn = cleanup_zero_choice_dups
purge_fully_inactive_dups_fn = purge_fully_inactive_dups
apply_safe_semantic_fixes_fn = apply_safe_semantic_fixes
