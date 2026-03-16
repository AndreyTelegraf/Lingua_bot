import json
import sqlite3
from pathlib import Path

from services.vocab_runtime.prior_reader import get_latest_vocab_prior_from_sqlite


def _prepare_db(path: Path) -> None:
    conn = sqlite3.connect(path)
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
    conn.close()


def test_get_latest_vocab_prior_reads_latest_finished_snapshot(tmp_path: Path):
    db = tmp_path / "test.db"
    _prepare_db(db)

    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO vocab_attempts (id, user_id, finished_at, result_snapshot_json) VALUES (?, ?, ?, ?)",
        (1, 100, "2026-03-01T10:00:00Z", json.dumps({"fresh_until_days": 90, "product_band": "A2"})),
    )
    conn.execute(
        "INSERT INTO vocab_attempts (id, user_id, finished_at, result_snapshot_json) VALUES (?, ?, ?, ?)",
        (2, 100, "2026-03-10T10:00:00Z", json.dumps({"fresh_until_days": 90, "product_band": "B1"})),
    )
    conn.commit()
    conn.close()

    got = get_latest_vocab_prior_from_sqlite(str(db), 100)
    assert got is not None
    assert got["attempt_id"] == 2
    assert got["snapshot"]["product_band"] == "B1"
    assert isinstance(got["is_usable_as_level_prior"], bool)


def test_get_latest_vocab_prior_ignores_unfinished_attempt(tmp_path: Path):
    db = tmp_path / "test.db"
    _prepare_db(db)

    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO vocab_attempts (id, user_id, finished_at, result_snapshot_json) VALUES (?, ?, ?, ?)",
        (1, 100, None, json.dumps({"fresh_until_days": 90, "product_band": "B1"})),
    )
    conn.commit()
    conn.close()

    got = get_latest_vocab_prior_from_sqlite(str(db), 100)
    assert got is None


def test_get_latest_vocab_prior_returns_none_for_missing_snapshot(tmp_path: Path):
    db = tmp_path / "test.db"
    _prepare_db(db)

    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO vocab_attempts (id, user_id, finished_at, result_snapshot_json) VALUES (?, ?, ?, ?)",
        (1, 100, "2026-03-10T10:00:00Z", None),
    )
    conn.commit()
    conn.close()

    got = get_latest_vocab_prior_from_sqlite(str(db), 100)
    assert got is None


def test_get_latest_vocab_prior_returns_none_for_malformed_snapshot(tmp_path: Path):
    db = tmp_path / "test.db"
    _prepare_db(db)

    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO vocab_attempts (id, user_id, finished_at, result_snapshot_json) VALUES (?, ?, ?, ?)",
        (1, 100, "2026-03-10T10:00:00Z", "{broken-json"),
    )
    conn.commit()
    conn.close()

    got = get_latest_vocab_prior_from_sqlite(str(db), 100)
    assert got is None
