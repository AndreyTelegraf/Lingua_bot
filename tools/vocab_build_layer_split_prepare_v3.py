from __future__ import annotations

import re
import shutil
import sqlite3
from pathlib import Path

ROOT = Path("/home/andrey/Projects/lingua_bot_v2")
RUNTIME_DB = ROOT / "data/lingua_staging.db"
BUILD_DB = ROOT / "data/vocab_build_workspace.db"
BACKUP_DIR = ROOT / "data/db_backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

BUILD_TABLES = [
    "vocab_raw_entries",
    "vocab_lemma_candidates",
    "vocab_item_validation",
]

FILES_TO_PATCH = [
    ROOT / "services/vocab_bank/ingest.py",
    ROOT / "services/vocab_bank/normalize.py",
    ROOT / "services/vocab_bank/merge.py",
    ROOT / "services/vocab_bank/build_items.py",
    ROOT / "services/vocab_bank/validate_items.py",
    ROOT / "services/vocab_bank/warmup.py",
    ROOT / "tools/build_openwordnet_safe_donor_report_v1.py",
    ROOT / "tools/build_openwordnet_overlap_report_v1.py",
    ROOT / "tools/ingest_openwordnet_to_vocab_raw_entries_v1.py",
    ROOT / "tools/audit_20k_verbs.py",
]

HELPER_PATH = ROOT / "services/vocab_bank/build_layer_db.py"

HELPER_CODE = """from __future__ import annotations

import os
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BUILD_DB = ROOT / "data/vocab_build_workspace.db"
BUILD_SCHEMA = "vbuild"

def get_build_db_path() -> Path:
    raw = os.getenv("LINGUA_VOCAB_BUILD_DB")
    return Path(raw) if raw else DEFAULT_BUILD_DB

def attach_build_db(conn: sqlite3.Connection) -> None:
    target = get_build_db_path()
    conn.execute(f"ATTACH DATABASE ? AS {BUILD_SCHEMA}", (str(target),))

def ensure_build_db_attached(conn: sqlite3.Connection) -> None:
    rows = conn.execute("PRAGMA database_list").fetchall()
    names = {row[1] for row in rows}
    if BUILD_SCHEMA not in names:
        attach_build_db(conn)
"""

TABLE_REPLACEMENTS = {
    r"(?<!vbuild\.)\bvocab_raw_entries\b": "vbuild.vocab_raw_entries",
    r"(?<!vbuild\.)\bvocab_lemma_candidates\b": "vbuild.vocab_lemma_candidates",
    r"(?<!vbuild\.)\bvocab_item_validation\b": "vbuild.vocab_item_validation",
}

def backup_file(src: Path, suffix: str) -> None:
    if src.exists():
        shutil.copy2(src, BACKUP_DIR / f"{src.name}.{suffix}.bak")

def copy_exact_schema_and_data() -> None:
    if BUILD_DB.exists():
        BUILD_DB.unlink()

    src = sqlite3.connect(RUNTIME_DB)
    try:
        ddl = {}
        idx = {}
        for table in BUILD_TABLES:
            row = src.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
                (table,),
            ).fetchone()
            if not row or not row[0]:
                raise SystemExit(f"missing CREATE TABLE for {table}")
            ddl[table] = row[0]

            idx_rows = src.execute(
                """
                SELECT sql
                FROM sqlite_master
                WHERE type='index' AND tbl_name=? AND sql IS NOT NULL
                ORDER BY name
                """,
                (table,),
            ).fetchall()
            idx[table] = [r[0] for r in idx_rows if r[0]]
    finally:
        src.close()

    dst = sqlite3.connect(BUILD_DB)
    try:
        for table in BUILD_TABLES:
            dst.execute(ddl[table])
            for sql in idx[table]:
                dst.execute(sql)

        dst.execute("ATTACH DATABASE ? AS srcdb", (str(RUNTIME_DB),))
        for table in BUILD_TABLES:
            dst.execute(f"INSERT INTO main.{table} SELECT * FROM srcdb.{table}")
        dst.commit()
        dst.execute("DETACH DATABASE srcdb")
    finally:
        dst.close()

def validate_counts() -> None:
    src = sqlite3.connect(RUNTIME_DB)
    dst = sqlite3.connect(BUILD_DB)
    try:
        for table in BUILD_TABLES:
            a = src.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            b = dst.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"{table}: runtime={a} build={b}")
            if a != b:
                raise SystemExit(f"row count mismatch for {table}: {a} != {b}")
    finally:
        src.close()
        dst.close()

def patch_file(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    original = text

    if "from services.vocab_bank.build_layer_db import ensure_build_db_attached" not in text:
        if "import sqlite3" in text:
            text = text.replace(
                "import sqlite3",
                "import sqlite3\nfrom services.vocab_bank.build_layer_db import ensure_build_db_attached",
                1,
            )

    if "ensure_build_db_attached(" not in text and "sqlite3.connect(" in text:
        text = re.sub(
            r"(?P<indent>[ \t]*)(?P<var>\w+)\s*=\s*sqlite3\.connect\((?P<args>[^\n]+)\)",
            r"\g<indent>\g<var> = sqlite3.connect(\g<args>)\n\g<indent>ensure_build_db_attached(\g<var>)",
            text,
            count=1,
        )

    for pattern, repl in TABLE_REPLACEMENTS.items():
        text = re.sub(pattern, repl, text)

    if text != original:
        path.write_text(text, encoding="utf-8")
        print(f"patched: {path.relative_to(ROOT)}")
    else:
        print(f"unchanged: {path.relative_to(ROOT)}")

def main() -> None:
    if not RUNTIME_DB.exists():
        raise SystemExit(f"runtime db not found: {RUNTIME_DB}")

    backup_file(RUNTIME_DB, "pre_build_split_v3")
    for f in FILES_TO_PATCH:
        backup_file(f, "pre_build_split_v3")

    HELPER_PATH.write_text(HELPER_CODE, encoding="utf-8")

    copy_exact_schema_and_data()
    validate_counts()

    for f in FILES_TO_PATCH:
        if f.exists():
            patch_file(f)
        else:
            print(f"skip missing: {f.relative_to(ROOT)}")

    print(f"build_db={BUILD_DB}")
    print("prepare v3 complete")
    print("runtime db still unchanged; prune later only after smoke")

if __name__ == "__main__":
    main()
