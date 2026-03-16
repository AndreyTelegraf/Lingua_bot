from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path


def test_write_vocab_snapshot_for_latest_finished_attempt(tmp_path: Path):
    db = tmp_path / "test.db"
    conn = sqlite3.connect(db)
    conn.execute(
        """
        CREATE TABLE vocab_attempts (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            finished_at TEXT NULL,
            range_min INTEGER,
            range_max INTEGER,
            correct_answers INTEGER,
            total_questions INTEGER,
            product_band TEXT,
            confidence TEXT,
            result_snapshot_json TEXT
        )
        """
    )
    conn.execute(
        """
        INSERT INTO vocab_attempts
        (id, user_id, finished_at, range_min, range_max, correct_answers, total_questions)
        VALUES
        (1, 100, '2026-03-16T12:00:00Z', 2500, 4000, 12, 24)
        """
    )
    conn.commit()
    conn.close()

    subprocess.run(
        [
            sys.executable,
            "tools/write_vocab_snapshot_for_latest_finished_attempt.py",
            "--db",
            str(db),
            "--user-id",
            "100",
        ],
        check=True,
    )

    conn = sqlite3.connect(db)
    row = conn.execute(
        """
        SELECT product_band, confidence, result_snapshot_json
        FROM vocab_attempts
        WHERE id = 1
        """
    ).fetchone()
    conn.close()

    assert row[0] == "B1"
    assert row[1] in {"low", "medium", "high"}
    payload = json.loads(row[2])
    assert payload["product_band"] == "B1"
    assert payload["prior_theta_hint"] == 0.2
