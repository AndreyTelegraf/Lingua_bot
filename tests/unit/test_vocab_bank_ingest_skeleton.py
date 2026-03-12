from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from services.vocab_bank.ingest import (
    ingest_entries,
    iter_csv_entries,
    iter_jsonl_entries,
    load_entries,
)


def _prepare_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE vocab_raw_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_name TEXT NOT NULL,
            external_key TEXT,
            raw_lemma TEXT,
            raw_pos TEXT,
            raw_level TEXT,
            raw_freq TEXT,
            raw_gloss_ru TEXT,
            payload_json TEXT NOT NULL DEFAULT '{}',
            ingested_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    return conn


def test_iter_csv_entries_smoke() -> None:
    path = Path("data/sources/sample_vocab_raw.csv")
    rows = iter_csv_entries(path, source_name="sample_csv")
    assert len(rows) == 3
    assert rows[0].source_name == "sample_csv"
    assert rows[0].raw_lemma == "casa"
    assert rows[1].raw_pos == "verb"
    assert rows[2].raw_gloss_ru == "рано"


def test_iter_jsonl_entries_smoke() -> None:
    path = Path("data/sources/sample_vocab_raw.jsonl")
    rows = iter_jsonl_entries(path, source_name="sample_jsonl")
    assert len(rows) == 2
    assert rows[0].raw_lemma == "janela"
    assert rows[1].raw_gloss_ru == "выбирать"


def test_load_entries_rejects_unknown_format() -> None:
    path = Path("data/sources/sample_vocab_raw.csv")
    try:
        load_entries(path, source_name="x", file_format="xml")
    except ValueError as exc:
        assert str(exc) == "unsupported_format:xml"
    else:
        raise AssertionError("unsupported format was not rejected")


def test_ingest_entries_inserts_rows() -> None:
    conn = _prepare_conn()
    try:
        rows = iter_csv_entries(Path("data/sources/sample_vocab_raw.csv"), source_name="sample_csv")
        inserted = ingest_entries(conn, entries=rows, truncate_source=False)
        assert inserted == 3

        cur = conn.execute(
            """
            SELECT source_name, external_key, raw_lemma, raw_pos, raw_level, raw_freq, raw_gloss_ru, payload_json
            FROM vocab_raw_entries
            ORDER BY id
            """
        )
        db_rows = cur.fetchall()
        assert len(db_rows) == 3
        assert db_rows[0][0] == "sample_csv"
        assert db_rows[0][2] == "casa"

        payload = json.loads(db_rows[0][7])
        assert payload["lemma"] == "casa"
    finally:
        conn.close()


def test_ingest_entries_truncate_source() -> None:
    conn = _prepare_conn()
    try:
        rows = iter_csv_entries(Path("data/sources/sample_vocab_raw.csv"), source_name="sample_csv")
        inserted1 = ingest_entries(conn, entries=rows, truncate_source=False)
        inserted2 = ingest_entries(conn, entries=rows[:1], truncate_source=True)
        assert inserted1 == 3
        assert inserted2 == 1

        cur = conn.execute("SELECT COUNT(*) FROM vocab_raw_entries WHERE source_name = 'sample_csv'")
        n = cur.fetchone()[0]
        assert n == 1
    finally:
        conn.close()
