from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.vocab_runtime.result_snapshot import build_vocab_result_snapshot


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--user-id", type=int, required=False)
    args = parser.parse_args()

    db_path = Path(args.db)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    where = "WHERE finished_at IS NOT NULL"
    params: tuple[object, ...] = ()
    if args.user_id is not None:
        where += " AND user_id = ?"
        params = (args.user_id,)

    row = conn.execute(
        f"""
        SELECT *
        FROM vocab_attempts
        {where}
        ORDER BY finished_at DESC, id DESC
        LIMIT 1
        """,
        params,
    ).fetchone()

    if row is None:
        print({"status": "no_finished_attempt"})
        conn.close()
        return

    required = ["range_min", "range_max", "correct_answers", "total_questions", "finished_at"]
    missing = [name for name in required if name not in row.keys()]
    if missing:
        print({"status": "missing_columns", "missing": missing, "attempt_id": row["id"]})
        conn.close()
        return

    snapshot = build_vocab_result_snapshot(
        range_min=int(row["range_min"]),
        range_max=int(row["range_max"]),
        correct_count=int(row["correct_answers"]),
        total_questions=int(row["total_questions"]),
        generated_at=row["finished_at"],
    )

    conn.execute(
        """
        UPDATE vocab_attempts
        SET product_band = ?,
            confidence = ?,
            result_snapshot_json = ?
        WHERE id = ?
        """,
        (
            snapshot.product_band,
            snapshot.confidence,
            snapshot.to_json_text(),
            row["id"],
        ),
    )
    conn.commit()

    print({
        "status": "ok",
        "attempt_id": row["id"],
        "product_band": snapshot.product_band,
        "confidence": snapshot.confidence,
    })
    conn.close()


if __name__ == "__main__":
    main()
