from __future__ import annotations

import json
import sqlite3


def _norm_text(value: str | None) -> str:
    return (value or "").strip().casefold()


def validate_and_publish_items(
    conn: sqlite3.Connection,
    *,
    topic_tag_prefix: str | None = None,
    build_code: str | None = None,
    publish: bool = True,
) -> int:
    conn.row_factory = sqlite3.Row

    if build_code:
        row = conn.execute(
            "SELECT id FROM vocab_builds WHERE build_code = ?",
            (build_code,),
        ).fetchone()
        if row is None:
            conn.execute(
                """
                INSERT INTO vocab_builds (
                    build_code, status, target_size, source_snapshot_json, config_json
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (build_code, "validating", None, "{}", "{}"),
            )
            build_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        else:
            build_id = int(row["id"])
            conn.execute(
                "DELETE FROM vocab_item_validation WHERE build_id = ?",
                (build_id,),
            )
            conn.execute(
                "UPDATE vocab_builds SET status = 'validating', finished_at = NULL WHERE id = ?",
                (build_id,),
            )
    else:
        conn.execute(
            """
            INSERT INTO vocab_builds (
                build_code, status, target_size, source_snapshot_json, config_json
            ) VALUES (?, ?, ?, ?, ?)
            """,
            ("adhoc_validation", "validating", None, "{}", "{}"),
        )
        build_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])

    sql = """
    SELECT id, lemma, correct_answer, topic_tag
    FROM vocab_items
    WHERE topic_tag LIKE 'build:%'
    """
    params: tuple[object, ...] = ()
    if topic_tag_prefix:
        sql += " AND topic_tag LIKE ?"
        params = (f"{topic_tag_prefix}%",)
    sql += " ORDER BY id"

    items = conn.execute(sql, params).fetchall()
    passed_count = 0

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

        rules: list[tuple[str, str, int, dict[str, object]]] = []

        choice_count = len(choices)
        correct_count = sum(int(row["is_correct"]) for row in choices)
        normalized = [_norm_text(str(row["choice_text"])) for row in choices]
        empty_exists = any(not x for x in normalized)
        dup_exists = len(normalized) != len(set(normalized))
        correct_text = _norm_text(str(item["correct_answer"]))
        correct_present = correct_text in normalized

        rules.append(("choice_count_eq_6", "hard", 1 if choice_count == 6 else 0, {"choice_count": choice_count}))
        rules.append(("correct_count_eq_1", "hard", 1 if correct_count == 1 else 0, {"correct_count": correct_count}))
        rules.append(("no_empty_choices", "hard", 1 if not empty_exists else 0, {"empty_exists": empty_exists}))
        rules.append(("no_duplicate_choices", "hard", 1 if not dup_exists else 0, {"duplicate_exists": dup_exists}))
        rules.append(("correct_present", "hard", 1 if correct_present else 0, {"correct_present": correct_present}))
        rules.append(
            ("correct_position_not_always_first", "soft", 1 if any(int(r["is_correct"]) == 1 and int(r["position_index"]) != 1 for r in choices) else 0,
             {"positions": [int(r["position_index"]) for r in choices if int(r["is_correct"]) == 1]}),
        )

        item_passed = True
        for rule_code, severity, passed, details in rules:
            if severity == "hard" and passed != 1:
                item_passed = False
            conn.execute(
                """
                INSERT INTO vocab_item_validation (
                    build_id, item_temp_id, rule_code, severity, passed, details_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    build_id,
                    str(item_id),
                    rule_code,
                    severity,
                    passed,
                    json.dumps(details, ensure_ascii=False, sort_keys=True),
                ),
            )

        if publish and item_passed:
            cur = conn.execute(
                """UPDATE vocab_items SET is_active = 1
WHERE id = ?
  AND (
    SELECT COUNT(*)
    FROM vocab_choices vc
    WHERE vc.item_id = vocab_items.id
  ) = 6
  AND (
    SELECT SUM(CASE WHEN COALESCE(vc.is_correct,0)=1 THEN 1 ELSE 0 END)
    FROM vocab_choices vc
    WHERE vc.item_id = vocab_items.id
  ) = 1
  AND (
    SELECT COUNT(DISTINCT TRIM(LOWER(vc.choice_text)))
    FROM vocab_choices vc
    WHERE vc.item_id = vocab_items.id
  ) = 6
  AND NOT EXISTS (
    SELECT 1
    FROM vocab_choices vc
    LEFT JOIN vocab_items vi2
      ON TRIM(LOWER(vi2.lemma)) = TRIM(LOWER(vc.choice_text))
    WHERE vc.item_id = vocab_items.id
      AND COALESCE(vc.is_correct,0) = 0
      AND vi2.id IS NULL
  )
  AND NOT EXISTS (
    SELECT 1
    FROM vocab_items v2
    WHERE v2.is_active = 1
      AND v2.id != vocab_items.id
      AND TRIM(LOWER(v2.lemma)) = TRIM(LOWER(vocab_items.lemma))
      AND COALESCE(TRIM(LOWER(v2.pos)), '') = COALESCE(TRIM(LOWER(vocab_items.pos)), '')
  )""",
                (item_id,),
            )
            if cur.rowcount == 1:
                passed_count += 1
        elif publish and not item_passed:
            conn.execute(
                """UPDATE vocab_items SET is_active = 0 WHERE id = ?""",
                (item_id,),
            )

    conn.execute(
        "UPDATE vocab_builds SET status = ?, finished_at = CURRENT_TIMESTAMP WHERE id = ?",
        ("validated", build_id),
    )
    conn.commit()
    return passed_count
