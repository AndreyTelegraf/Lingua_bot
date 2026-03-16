from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path


def test_apply_vocab_attempt_handoff_columns_sqlite(tmp_path: Path):
    db = tmp_path / "test.db"
    conn = sqlite3.connect(db)
    conn.execute(
        """
        CREATE TABLE vocab_attempts (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            finished_at TEXT NULL
        )
        """
    )
    conn.commit()
    conn.close()

    subprocess.run(
        [
            sys.executable,
            "tools/apply_vocab_attempt_handoff_columns_sqlite.py",
            "--db",
            str(db),
        ],
        check=True,
    )

    conn = sqlite3.connect(db)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(vocab_attempts)").fetchall()}
    conn.close()

    assert "product_band" in cols
    assert "confidence" in cols
    assert "result_snapshot_json" in cols
