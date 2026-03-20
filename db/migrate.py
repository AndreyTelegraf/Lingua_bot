from __future__ import annotations

import asyncio
from pathlib import Path

import aiosqlite

from app.config import get_settings


MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations_sqlite"


async def _table_exists(conn: aiosqlite.Connection, name: str) -> bool:
    cur = await conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (name,),
    )
    row = await cur.fetchone()
    return row is not None


async def _table_columns(conn: aiosqlite.Connection, name: str) -> list[str]:
    cur = await conn.execute(f"PRAGMA table_info({name})")
    rows = await cur.fetchall()
    return [str(r[1]) for r in rows]


async def _ensure_schema_migrations(conn: aiosqlite.Connection) -> None:
    exists = await _table_exists(conn, "schema_migrations")
    if not exists:
        await conn.execute(
            """
            CREATE TABLE schema_migrations (
                filename TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await conn.commit()
        return

    cols = await _table_columns(conn, "schema_migrations")
    if "filename" in cols and "applied_at" in cols:
        return

    if not await _table_exists(conn, "schema_migrations_legacy"):
        await conn.execute("ALTER TABLE schema_migrations RENAME TO schema_migrations_legacy")
    else:
        await conn.execute("DROP TABLE schema_migrations")

    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            filename TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    await conn.commit()


async def _db_looks_initialized(conn: aiosqlite.Connection) -> bool:
    cur = await conn.execute(
        """
        SELECT COUNT(*)
        FROM sqlite_master
        WHERE type='table'
          AND name NOT LIKE 'sqlite_%'
          AND name NOT IN ('schema_migrations', 'schema_migrations_legacy')
        """
    )
    row = await cur.fetchone()
    return bool(row and int(row[0]) > 0)


async def _get_applied(conn: aiosqlite.Connection) -> set[str]:
    cols = await _table_columns(conn, "schema_migrations")
    if "filename" not in cols:
        return set()
    cur = await conn.execute("SELECT filename FROM schema_migrations")
    rows = await cur.fetchall()
    return {str(r[0]) for r in rows if r and r[0] is not None}


async def _mark_applied(conn: aiosqlite.Connection, filename: str) -> None:
    await conn.execute(
        "INSERT OR IGNORE INTO schema_migrations(filename) VALUES (?)",
        (filename,),
    )
    await conn.commit()


async def _bootstrap_existing_db(conn: aiosqlite.Connection) -> None:
    files = sorted(p.name for p in MIGRATIONS_DIR.glob("*.sql"))
    for name in files:
        await conn.execute(
            "INSERT OR IGNORE INTO schema_migrations(filename) VALUES (?)",
            (name,),
        )
    await conn.commit()


async def apply_migrations() -> None:
    settings = get_settings()
    db_path = Path(settings.db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(db_path.as_posix()) as conn:
        await _ensure_schema_migrations(conn)

        applied = await _get_applied(conn)
        initialized = await _db_looks_initialized(conn)

        if initialized and not applied:
            await _bootstrap_existing_db(conn)
            applied = await _get_applied(conn)

        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if path.name in applied:
                continue
            sql = path.read_text(encoding="utf-8")
            await conn.executescript(sql)
            await _mark_applied(conn, path.name)


if __name__ == "__main__":
    asyncio.run(apply_migrations())
