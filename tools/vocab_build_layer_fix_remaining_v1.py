from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path("/home/andrey/Projects/lingua_bot_v2")
BACKUP_DIR = ROOT / "data/db_backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

FILES = [
    ROOT / "services/vocab_bank/ingest.py",
    ROOT / "services/vocab_bank/normalize.py",
    ROOT / "services/vocab_bank/merge.py",
    ROOT / "services/vocab_bank/validate_items.py",
]

def backup(path: Path) -> None:
    if path.exists():
        shutil.copy2(path, BACKUP_DIR / f"{path.name}.fix_remaining_v1.bak")

def patch_text(path: Path, replacements: list[tuple[str, str]]) -> None:
    text = path.read_text(encoding="utf-8")
    original = text
    for old, new in replacements:
        if old in text:
            text = text.replace(old, new)
    if text != original:
        path.write_text(text, encoding="utf-8")
        print(f"patched: {path.relative_to(ROOT)}")
    else:
        print(f"unchanged: {path.relative_to(ROOT)}")

for f in FILES:
    backup(f)

patch_text(
    ROOT / "services/vocab_bank/ingest.py",
    [
        (
            '        conn.executemany(\n            "DELETE FROM {raw_entries_table} WHERE source_name = ?",\n            [(name,) for name in source_names],\n        )\n',
            '        conn.executemany(\n            f"DELETE FROM {raw_entries_table} WHERE source_name = ?",\n            [(name,) for name in source_names],\n        )\n',
        ),
    ],
)

patch_text(
    ROOT / "services/vocab_bank/normalize.py",
    [
        (
            '        conn.executemany(\n            "DELETE FROM {lemma_candidates_table} WHERE source_name = ?",\n            [(name,) for name in source_names],\n        )\n',
            '        conn.executemany(\n            f"DELETE FROM {lemma_candidates_table} WHERE source_name = ?",\n            [(name,) for name in source_names],\n        )\n',
        ),
    ],
)

patch_text(
    ROOT / "services/vocab_bank/merge.py",
    [
        (
            '        conn.execute(\n            """\n            UPDATE {lemma_candidates_table}\n            SET\n',
            '        conn.execute(\n            f"""\n            UPDATE {lemma_candidates_table}\n            SET\n',
        ),
        (
            '            conn.execute(\n                """\n                UPDATE {lemma_candidates_table}\n                SET\n',
            '            conn.execute(\n                f"""\n                UPDATE {lemma_candidates_table}\n                SET\n',
        ),
    ],
)

patch_text(
    ROOT / "services/vocab_bank/validate_items.py",
    [
        (
            '        item_passed = True\n        for rule_code, severity, passed, details in rules:\n            if severity == "hard" and passed != 1:\n                item_passed = False\n',
            '        item_passed = all(passed == 1 for _, severity, passed, _ in rules if severity == "hard")\n        for rule_code, severity, passed, details in rules:\n',
        ),
    ],
)
