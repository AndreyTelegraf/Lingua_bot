from __future__ import annotations

from pathlib import Path

ROOT = Path("/home/andrey/Projects/lingua_bot_v2")

HELPER = ROOT / "services/vocab_bank/build_layer_db.py"
FILES = {
    "services/vocab_bank/ingest.py": [
        (
            "from services.vocab_bank.build_layer_db import ensure_build_db_attached",
            "from services.vocab_bank.build_layer_db import ensure_build_db_attached, resolve_build_table",
        ),
        (
            "    rows = list(entries)\n    if not rows:\n        return 0\n",
            "    rows = list(entries)\n    if not rows:\n        return 0\n\n    raw_entries_table = resolve_build_table(conn, \"vocab_raw_entries\")\n",
        ),
        ('"DELETE FROM vbuild.vocab_raw_entries WHERE source_name = ?"', '"DELETE FROM {raw_entries_table} WHERE source_name = ?"'),
        ("INSERT INTO vbuild.vocab_raw_entries (", "INSERT INTO {raw_entries_table} ("),
        ('conn.executemany(\n        """', 'conn.executemany(\n        f"""'),
    ],
    "services/vocab_bank/normalize.py": [
        (
            "from services.vocab_bank.build_layer_db import ensure_build_db_attached",
            "from services.vocab_bank.build_layer_db import ensure_build_db_attached, resolve_build_table",
        ),
        (
            "def normalize_raw_entries_to_candidates(\n    conn: sqlite3.Connection,\n    *,\n    source_name: str | None = None,\n    truncate_source: bool = False,\n) -> int:\n    conn.row_factory = sqlite3.Row\n",
            "def normalize_raw_entries_to_candidates(\n    conn: sqlite3.Connection,\n    *,\n    source_name: str | None = None,\n    truncate_source: bool = False,\n) -> int:\n    conn.row_factory = sqlite3.Row\n\n    raw_entries_table = resolve_build_table(conn, \"vocab_raw_entries\")\n    lemma_candidates_table = resolve_build_table(conn, \"vocab_lemma_candidates\")\n",
        ),
        ("FROM vbuild.vocab_raw_entries", "FROM {raw_entries_table}"),
        ("DELETE FROM vbuild.vocab_lemma_candidates WHERE source_name = ?", "DELETE FROM {lemma_candidates_table} WHERE source_name = ?"),
        ("INSERT INTO vbuild.vocab_lemma_candidates (", "INSERT INTO {lemma_candidates_table} ("),
        ('sql = """', 'sql = f"""'),
        ('conn.execute(\n            """\n            DELETE FROM {lemma_candidates_table} WHERE source_name = ?\n            """', 'conn.execute(\n            f"""\n            DELETE FROM {lemma_candidates_table} WHERE source_name = ?\n            """'),
        ('conn.executemany(\n        """\n        INSERT INTO {lemma_candidates_table} (', 'conn.executemany(\n        f"""\n        INSERT INTO {lemma_candidates_table} ('),
    ],
    "services/vocab_bank/merge.py": [
        (
            "from services.vocab_bank.build_layer_db import ensure_build_db_attached",
            "from services.vocab_bank.build_layer_db import ensure_build_db_attached, resolve_build_table",
        ),
        (
            "def merge_candidates_for_source(\n    conn: sqlite3.Connection,\n    *,\n    source_name: str | None = None,\n) -> int:\n    conn.row_factory = sqlite3.Row\n",
            "def merge_candidates_for_source(\n    conn: sqlite3.Connection,\n    *,\n    source_name: str | None = None,\n) -> int:\n    conn.row_factory = sqlite3.Row\n\n    lemma_candidates_table = resolve_build_table(conn, \"vocab_lemma_candidates\")\n",
        ),
        ("FROM vbuild.vocab_lemma_candidates", "FROM {lemma_candidates_table}"),
        ("UPDATE vbuild.vocab_lemma_candidates", "UPDATE {lemma_candidates_table}"),
        ('sql = """', 'sql = f"""'),
        ('conn.execute(\n                """\n                UPDATE {lemma_candidates_table}', 'conn.execute(\n                f"""\n                UPDATE {lemma_candidates_table}'),
    ],
    "services/vocab_bank/build_items.py": [
        (
            "from services.vocab_bank.build_layer_db import ensure_build_db_attached",
            "from services.vocab_bank.build_layer_db import ensure_build_db_attached, resolve_build_table",
        ),
        (
            "def build_vocab_items_from_candidates(\n    conn: sqlite3.Connection,\n    *,\n    source_name: str | None = None,\n    truncate_topic_prefix: str | None = None,\n) -> int:\n    conn.row_factory = sqlite3.Row\n",
            "def build_vocab_items_from_candidates(\n    conn: sqlite3.Connection,\n    *,\n    source_name: str | None = None,\n    truncate_topic_prefix: str | None = None,\n) -> int:\n    conn.row_factory = sqlite3.Row\n\n    lemma_candidates_table = resolve_build_table(conn, \"vocab_lemma_candidates\")\n",
        ),
        ("FROM vbuild.vocab_lemma_candidates", "FROM {lemma_candidates_table}"),
        ('sql = """', 'sql = f"""'),
    ],
    "services/vocab_bank/validate_items.py": [
        (
            "from services.vocab_bank.build_layer_db import ensure_build_db_attached",
            "from services.vocab_bank.build_layer_db import ensure_build_db_attached, resolve_build_table",
        ),
        (
            "def validate_and_publish_items(\n    conn: sqlite3.Connection,\n    *,\n    topic_tag_prefix: str | None = None,\n    build_code: str | None = None,\n    publish: bool = True,\n) -> int:\n    conn.row_factory = sqlite3.Row\n",
            "def validate_and_publish_items(\n    conn: sqlite3.Connection,\n    *,\n    topic_tag_prefix: str | None = None,\n    build_code: str | None = None,\n    publish: bool = True,\n) -> int:\n    conn.row_factory = sqlite3.Row\n\n    item_validation_table = resolve_build_table(conn, \"vocab_item_validation\")\n",
        ),
        ('"DELETE FROM vbuild.vocab_item_validation WHERE build_id = ?"', '"DELETE FROM {item_validation_table} WHERE build_id = ?"'),
        ("INSERT INTO vbuild.vocab_item_validation (", "INSERT INTO {item_validation_table} ("),
        ('conn.execute(\n                """\n                DELETE FROM {item_validation_table} WHERE build_id = ?\n                """', 'conn.execute(\n                f"""\n                DELETE FROM {item_validation_table} WHERE build_id = ?\n                """'),
        ('conn.execute(\n                """\n                INSERT INTO {item_validation_table} (', 'conn.execute(\n                f"""\n                INSERT INTO {item_validation_table} ('),
    ],
    "services/vocab_bank/warmup.py": [
        (
            "from services.vocab_bank.build_layer_db import ensure_build_db_attached",
            "from services.vocab_bank.build_layer_db import ensure_build_db_attached, resolve_build_table",
        ),
        (
            "def persist_warmup_validation_summary(\n    conn: sqlite3.Connection,\n    *,\n    build_code: str,\n    report: dict[str, object],\n) -> None:\n    conn.row_factory = sqlite3.Row\n",
            "def persist_warmup_validation_summary(\n    conn: sqlite3.Connection,\n    *,\n    build_code: str,\n    report: dict[str, object],\n) -> None:\n    conn.row_factory = sqlite3.Row\n\n    item_validation_table = resolve_build_table(conn, \"vocab_item_validation\")\n",
        ),
        ("INSERT INTO vbuild.vocab_item_validation (", "INSERT INTO {item_validation_table} ("),
        ('conn.execute(\n        """\n        INSERT INTO {item_validation_table} (', 'conn.execute(\n        f"""\n        INSERT INTO {item_validation_table} ('),
    ],
}

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
        main_path = ""
        for row in rows:
            if row[1] == "main":
                main_path = row[2] or ""
                break
        if main_path not in ("", ":memory:"):
            attach_build_db(conn)

def _table_exists(conn: sqlite3.Connection, schema: str, table: str) -> bool:
    rows = conn.execute(f"PRAGMA {schema}.table_info({table})").fetchall()
    return bool(rows)

def resolve_build_table(conn: sqlite3.Connection, table: str) -> str:
    ensure_build_db_attached(conn)
    if _table_exists(conn, BUILD_SCHEMA, table):
        return f"{BUILD_SCHEMA}.{table}"
    if _table_exists(conn, "main", table):
        return table
    raise RuntimeError(f"table_not_found:{table}")
"""
def patch(path: Path, replacements: list[tuple[str, str]]) -> None:
    text = path.read_text(encoding="utf-8")
    original = text
    for old, new in replacements:
        if old in text:
            text = text.replace(old, new)
    if text == original:
        print(f"unchanged: {path.relative_to(ROOT)}")
    else:
        path.write_text(text, encoding="utf-8")
        print(f"patched: {path.relative_to(ROOT)}")

def main() -> None:
    HELPER.write_text(HELPER_CODE, encoding="utf-8")
    print(f"patched: {HELPER.relative_to(ROOT)}")
    for rel, replacements in FILES.items():
        patch(ROOT / rel, replacements)

if __name__ == "__main__":
    main()
