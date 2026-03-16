from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from services.vocab_runtime.prior_reader import get_latest_vocab_prior


def _prepare_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE vocab_attempts (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            finished_at TEXT NULL,
            result_snapshot_json TEXT NULL
        )
        """
    )
    conn.commit()
    return conn


def test_get_latest_vocab_prior_accepts_connection(tmp_path: Path):
    db = tmp_path / "test.db"
    conn = _prepare_db(db)
    conn.execute(
        "INSERT INTO vocab_attempts (id, user_id, finished_at, result_snapshot_json) VALUES (?, ?, ?, ?)",
        (1, 42, "2026-03-16T12:00:00Z", json.dumps({"fresh_until_days": 90, "product_band": "B1"})),
    )
    conn.commit()

    got = get_latest_vocab_prior(conn, user_id=42)
    assert got is not None
    assert got["attempt_id"] == 1
    assert got["snapshot"]["product_band"] == "B1"

    conn.close()
