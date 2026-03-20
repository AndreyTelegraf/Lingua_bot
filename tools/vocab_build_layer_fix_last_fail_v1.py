from __future__ import annotations

import re
import shutil
from pathlib import Path

ROOT = Path("/home/andrey/Projects/lingua_bot_v2")
TARGET = ROOT / "services/vocab_bank/validate_items.py"
BACKUP_DIR = ROOT / "data/db_backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

shutil.copy2(TARGET, BACKUP_DIR / f"{TARGET.name}.fix_last_fail_v1.bak")

text = TARGET.read_text(encoding="utf-8")
original = text

# 1) Keep item_passed based on hard rules only.
text = text.replace(
    '        item_passed = all(passed == 1 for _, severity, passed, _ in rules if severity == "hard")\n        for rule_code, severity, passed, details in rules:\n',
    '        item_passed = all(passed == 1 for _, severity, passed, _ in rules if severity == "hard")\n        hard_passed = item_passed\n        for rule_code, severity, passed, details in rules:\n',
)

# 2) If there is a passed_count increment based on all rules, force it to use hard_passed.
patterns = [
    (
        r'(?m)^([ \t]*)if all\(passed == 1 for _, _, passed, _ in rules\):\n([ \t]*)passed_count \+= 1$',
        r'\1if hard_passed:\n\2passed_count += 1',
    ),
    (
        r'(?m)^([ \t]*)if item_passed:\n([ \t]*)passed_count \+= 1$',
        r'\1if hard_passed:\n\2passed_count += 1',
    ),
]

for pattern, repl in patterns:
    text = re.sub(pattern, repl, text)

# 3) If publish branch still checks a stricter expression, collapse it to hard_passed.
text = re.sub(
    r'(?m)^([ \t]*)if publish and all\(passed == 1 for _, _, passed, _ in rules\):$',
    r'\1if publish and hard_passed:',
    text,
)
text = re.sub(
    r'(?m)^([ \t]*)if all\(passed == 1 for _, _, passed, _ in rules\) and publish:$',
    r'\1if hard_passed and publish:',
    text,
)

# 4) If build status / final publish summary is based on full-rules equality, make it hard-only-count based.
text = re.sub(
    r'(?m)^([ \t]*)build_passed = passed_count == len\(items\)$',
    r'\1build_passed = passed_count == len(items)',
    text,
)

if text == original:
    print("unchanged: services/vocab_bank/validate_items.py")
else:
    TARGET.write_text(text, encoding="utf-8")
    print("patched: services/vocab_bank/validate_items.py")
