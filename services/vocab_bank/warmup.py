from __future__ import annotations

import json
import sqlite3


def run_warmup_report(
    conn: sqlite3.Connection,
    *,
    topic_tag_prefix: str | None = None,
) -> dict[str, object]:
    conn.row_factory = sqlite3.Row

    sql = """
    SELECT id, lemma, topic_tag, is_active
    FROM vocab_items
    WHERE topic_tag LIKE 'build:%'
    """
    params: tuple[object, ...] = ()
    if topic_tag_prefix:
        sql += " AND topic_tag LIKE ?"
        params = (f"{topic_tag_prefix}%",)
    sql += " ORDER BY id"

    items = conn.execute(sql, params).fetchall()

    shown = 0
    passed = 0
    failed = 0
    details: list[dict[str, object]] = []

    for item in items:
        item_id = int(item["id"])
        choices = conn.execute(
            """
            SELECT choice_text, is_correct, position_index
            FROM vocab_choices
            WHERE item_id = ?
            ORDER BY position_index
            """,
            (item_id,),
        ).fetchall()

        choice_count = len(choices)
        correct_count = sum(int(r["is_correct"]) for r in choices)
        choice_texts = [str(r["choice_text"]).strip().casefold() for r in choices]
        duplicate_exists = len(choice_texts) != len(set(choice_texts))
        empty_exists = any(not t for t in choice_texts)

        ok = (
            int(item["is_active"]) == 1
            and choice_count == 6
            and correct_count == 1
            and not duplicate_exists
            and not empty_exists
        )

        shown += 1
        if ok:
            passed += 1
        else:
            failed += 1

        details.append(
            {
                "item_id": item_id,
                "lemma": str(item["lemma"]),
                "topic_tag": str(item["topic_tag"]),
                "is_active": int(item["is_active"]),
                "choice_count": choice_count,
                "correct_count": correct_count,
                "duplicate_exists": duplicate_exists,
                "empty_exists": empty_exists,
                "ok": ok,
            }
        )

    return {
        "shown": shown,
        "passed": passed,
        "failed": failed,
        "pass_rate": (passed / shown) if shown else 0.0,
        "details": details,
    }


def persist_warmup_validation_summary(
    conn: sqlite3.Connection,
    *,
    build_code: str,
    report: dict[str, object],
) -> None:
    conn.row_factory = sqlite3.Row

    row = conn.execute(
        "SELECT id FROM vocab_builds WHERE build_code = ?",
        (build_code,),
    ).fetchone()
    if row is None:
        raise RuntimeError("build_code_not_found")

    build_id = int(row["id"])
    conn.execute(
        """
        INSERT INTO vocab_item_validation (
            build_id, item_temp_id, rule_code, severity, passed, details_json
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            build_id,
            None,
            "warmup_summary",
            "info",
            1,
            json.dumps(report, ensure_ascii=False, sort_keys=True),
        ),
    )
    conn.commit()
