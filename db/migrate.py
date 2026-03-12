from __future__ import annotations

import asyncio
from pathlib import Path

from db.connection import open_db


MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations_sqlite"


CREATE_SCHEMA_MIGRATIONS_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


async def ensure_schema_migrations() -> None:
    conn = await open_db()
    try:
        await conn.execute(CREATE_SCHEMA_MIGRATIONS_SQL)
        await conn.commit()
    finally:
        await conn.close()


async def get_applied_versions() -> set[str]:
    conn = await open_db()
    try:
        await conn.execute(CREATE_SCHEMA_MIGRATIONS_SQL)
        cursor = await conn.execute("SELECT version FROM schema_migrations ORDER BY version;")
        rows = await cursor.fetchall()
        return {str(row["version"]) for row in rows}
    finally:
        await conn.close()


async def apply_migrations() -> list[str]:
    await ensure_schema_migrations()
    applied = await get_applied_versions()
    files = sorted(p for p in MIGRATIONS_DIR.glob("*.sql") if p.is_file())

    applied_now: list[str] = []

    conn = await open_db()
    try:
        await conn.execute("BEGIN;")
        for path in files:
            version = path.name
            if version in applied:
                continue

            sql = path.read_text(encoding="utf-8")
            await conn.executescript(sql)
            await conn.execute(
                "INSERT INTO schema_migrations(version) VALUES (?);",
                (version,),
            )
            applied_now.append(version)

        await conn.commit()
        return applied_now
    except Exception:
        await conn.rollback()
        raise
    finally:
        await conn.close()


async def main() -> None:
    applied_now = await apply_migrations()
    if applied_now:
        print("applied:")
        for version in applied_now:
            print(version)
    else:
        print("no pending migrations")


if __name__ == "__main__":
    asyncio.run(main())
