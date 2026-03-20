from __future__ import annotations

import os
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BUILD_DB = ROOT / "data/vocab_build_workspace.db"
BUILD_SCHEMA = "vbuild"

def get_build_db_path() -> Path:
    raw = os.getenv("LINGUA_VOCAB_BUILD_DB")
    return Path(raw) if raw else DEFAULT_BUILD_DB

def _attached_schema_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("PRAGMA database_list").fetchall()
    return {row[1] for row in rows}

def attach_build_db(conn: sqlite3.Connection) -> None:
    target = get_build_db_path()
    conn.execute(f"ATTACH DATABASE ? AS {BUILD_SCHEMA}", (str(target),))

def ensure_build_db_attached(conn: sqlite3.Connection) -> None:
    rows = conn.execute("PRAGMA database_list").fetchall()
    names = {row[1] for row in rows}
    if BUILD_SCHEMA in names:
        return

    main_path = ""
    for row in rows:
        if row[1] == "main":
            main_path = row[2] or ""
            break

    if main_path not in ("", ":memory:"):
        attach_build_db(conn)

def _table_exists(conn: sqlite3.Connection, schema: str, table: str) -> bool:
    if schema not in _attached_schema_names(conn):
        return False
    rows = conn.execute(f"PRAGMA {schema}.table_info({table})").fetchall()
    return bool(rows)

def resolve_build_table(conn: sqlite3.Connection, table: str) -> str:
    ensure_build_db_attached(conn)

    if _table_exists(conn, BUILD_SCHEMA, table):
        return f"{BUILD_SCHEMA}.{table}"

    if _table_exists(conn, "main", table):
        return table

    raise RuntimeError(f"table_not_found:{table}")
