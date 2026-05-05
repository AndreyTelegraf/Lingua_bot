from __future__ import annotations

import sqlite3
from pathlib import Path

from services.vocab4.authoring import EXPECTED_COLUMNS, import_authoring_csv_text
from services.vocab4.certification import load_pending_authoring_items
from scripts.vocab4_review_cli import format_item, review_loop

MIGRATION = Path("db/migrations_sqlite/020_vocab4_runtime.sql")

_HEADER = ",".join(EXPECTED_COLUMNS)
_ROW_1 = "casa,noun,1K,What does this mean?,house,home,building,place,structure,dwelling,test_source,author1"
_ROW_2 = "libro,noun,1K,What does this mean?,book,page,text,object,notebook,volume,test_source,author1"


def _build_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(MIGRATION.read_text(encoding="utf-8"))
    return conn


def _seed(conn: sqlite3.Connection, *rows: str) -> list[int]:
    csv_text = "\n".join([_HEADER] + list(rows))
    import_authoring_csv_text(conn, csv_text, dry_run=False)
    return [r[0] for r in conn.execute("SELECT id FROM vocab4_authoring_items ORDER BY id ASC").fetchall()]


def _make_input(*responses: str):
    it = iter(responses)
    return lambda _prompt: next(it)


# --- test 1 ---

def test_cli_lists_pending_items() -> None:
    conn = _build_conn()
    _seed(conn, _ROW_1)
    items = load_pending_authoring_items(conn)
    output = format_item(items[0])
    assert "[ID:" in output
    assert "lemma: casa" in output
    assert "house" in output
    assert "home" in output
    assert "(correct)" in output
    assert "source: test_source" in output


# --- test 2 ---

def test_cli_promote_path_calls_certification() -> None:
    conn = _build_conn()
    _seed(conn, _ROW_1)
    review_loop(conn, input_fn=_make_input("a"))
    assert conn.execute("SELECT COUNT(*) FROM vocab4_items").fetchone()[0] == 1


# --- test 3 ---

def test_cli_reject_path_calls_certification() -> None:
    conn = _build_conn()
    _seed(conn, _ROW_1)
    review_loop(conn, input_fn=_make_input("r", "bad distractors"))
    row = conn.execute("SELECT cert_status FROM vocab4_authoring_items").fetchone()
    assert row["cert_status"] == "rejected"


# --- test 4 ---

def test_cli_skip_does_not_modify() -> None:
    conn = _build_conn()
    _seed(conn, _ROW_1)
    review_loop(conn, input_fn=_make_input("s"))
    row = conn.execute("SELECT cert_status FROM vocab4_authoring_items").fetchone()
    assert row["cert_status"] == "pending"
    assert conn.execute("SELECT COUNT(*) FROM vocab4_items").fetchone()[0] == 0


# --- test 5 ---

def test_cli_quit_stops_loop() -> None:
    conn = _build_conn()
    _seed(conn, _ROW_1, _ROW_2)
    review_loop(conn, input_fn=_make_input("q"))
    pending = conn.execute(
        "SELECT COUNT(*) FROM vocab4_authoring_items WHERE cert_status='pending'"
    ).fetchone()[0]
    assert pending == 2
