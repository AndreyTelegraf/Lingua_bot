from __future__ import annotations

import re
import shutil
from pathlib import Path

ROOT = Path("/home/andrey/Projects/lingua_bot_v2")
TARGET = ROOT / "services/vocab_bank/validate_items.py"
BACKUP_DIR = ROOT / "data/db_backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

shutil.copy2(TARGET, BACKUP_DIR / f"{TARGET.name}.fix_publish_gate_v1.bak")

text = TARGET.read_text(encoding="utf-8")
original = text

pattern = re.compile(
    r"""
[ \t]*AND\ NOT\ EXISTS\ \(
\s*SELECT\ 1
\s*FROM\ vocab_choices\ vc
\s*LEFT\ JOIN\ vocab_items\ vi2
\s*ON\ TRIM\(LOWER\(vi2\.lemma\)\)\ =\ TRIM\(LOWER\(vc\.choice_text\)\)
\s*WHERE\ vc\.item_id\ =\ vocab_items\.id
\s*AND\ COALESCE\(vc\.is_correct,0\)\ =\ 0
\s*AND\ vi2\.id\ IS\ NULL
\s*\)
""",
    re.VERBOSE,
)

text, n = pattern.subn("", text, count=1)

if n != 1:
    raise SystemExit("expected publish-gate block not found exactly once")

TARGET.write_text(text, encoding="utf-8")
print("patched: services/vocab_bank/validate_items.py")
