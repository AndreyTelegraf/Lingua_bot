from __future__ import annotations

import csv
import sys
from pathlib import Path

REQUIRED = [
    "lemma",
    "pos",
    "bin_name",
    "prompt",
    "correct_choice",
    "distractor_1",
    "distractor_2",
    "distractor_3",
    "distractor_4",
    "distractor_5",
    "source_note",
    "author_note",
    "audit_status",
    "audit_reasons",
]

ALLOWED_POS = {"noun", "verb", "adjective", "adverb"}
ALLOWED_BINS = {"1K", "2K", "5K", "10K", "20K"}
ALLOWED_AUDIT = {"candidate", "rejected", "needs_rewrite", "certified", "retired"}

def fail(msg: str) -> None:
    raise SystemExit(f"FAIL: {msg}")

def validate_path(path: Path) -> None:
    if not path.exists():
        fail(f"missing file: {path}")

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != REQUIRED:
            fail(f"bad header: {reader.fieldnames!r}")

        seen: set[tuple[str, str]] = set()
        rows = list(reader)

    for i, row in enumerate(rows, start=2):
        lemma = (row.get("lemma") or "").strip()
        pos = (row.get("pos") or "").strip()
        bin_name = (row.get("bin_name") or "").strip()
        audit_status = (row.get("audit_status") or "").strip()

        if not lemma:
            fail(f"row {i}: empty lemma")
        if pos not in ALLOWED_POS:
            fail(f"row {i}: bad pos={pos!r}")
        if bin_name not in ALLOWED_BINS:
            fail(f"row {i}: bad bin_name={bin_name!r}")
        if audit_status not in ALLOWED_AUDIT:
            fail(f"row {i}: bad audit_status={audit_status!r}")

        choices = [
            (row.get("correct_choice") or "").strip(),
            (row.get("distractor_1") or "").strip(),
            (row.get("distractor_2") or "").strip(),
            (row.get("distractor_3") or "").strip(),
            (row.get("distractor_4") or "").strip(),
            (row.get("distractor_5") or "").strip(),
        ]
        if any(not x for x in choices):
            fail(f"row {i}: empty choice")
        if len({x.casefold() for x in choices}) != 6:
            fail(f"row {i}: duplicate choices")

        key = (lemma.casefold(), pos)
        if key in seen:
            fail(f"row {i}: duplicate lemma+pos {key}")
        seen.add(key)

    print(f"PASS: {path} rows={len(rows)}")

def main() -> None:
    if len(sys.argv) != 2:
        fail("usage: validate_authoring_csv.py <csv_path>")

    validate_path(Path(sys.argv[1]))

if __name__ == "__main__":
    main()
