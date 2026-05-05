from __future__ import annotations

import csv
import io
import json
import sqlite3

EXPECTED_COLUMNS: list[str] = [
    "lemma", "pos", "bin_name", "prompt", "correct_choice",
    "distractor_1", "distractor_2", "distractor_3", "distractor_4", "distractor_5",
    "source_note", "author_note",
]

VALID_POS:  frozenset[str] = frozenset({"noun", "verb", "adjective", "adverb"})
VALID_BINS: frozenset[str] = frozenset({"1K", "2K", "5K", "10K", "20K"})

_DISTRACTOR_KEYS = ["distractor_1", "distractor_2", "distractor_3", "distractor_4", "distractor_5"]


def _err(row: int, code: str, message: str) -> dict:
    return {"row": row, "code": code, "message": message}


def _validate_row(row_num: int, row: dict) -> list[dict]:
    errors: list[dict] = []

    lemma = row["lemma"].strip()
    if not lemma:
        errors.append(_err(row_num, "empty_lemma", "lemma is empty"))

    pos = row["pos"].strip()
    if pos not in VALID_POS:
        errors.append(_err(row_num, "bad_pos", f"pos={pos!r} not in {sorted(VALID_POS)}"))

    bin_name = row["bin_name"].strip()
    if bin_name not in VALID_BINS:
        errors.append(_err(row_num, "bad_bin_name", f"bin_name={bin_name!r} not in {sorted(VALID_BINS)}"))

    if not row["prompt"].strip():
        errors.append(_err(row_num, "empty_prompt", "prompt is empty"))

    correct = row["correct_choice"].strip()
    correct_empty = not correct
    if correct_empty:
        errors.append(_err(row_num, "empty_correct_choice", "correct_choice is empty"))

    distractor_empty = False
    for key in _DISTRACTOR_KEYS:
        if not row[key].strip():
            errors.append(_err(row_num, "empty_distractor", f"{key} is empty"))
            distractor_empty = True

    if not row["source_note"].strip():
        errors.append(_err(row_num, "empty_source_note", "source_note is empty"))

    # duplicate check only when correct_choice and all distractors are non-empty
    if not correct_empty and not distractor_empty:
        choices = [correct] + [row[k].strip() for k in _DISTRACTOR_KEYS]
        lower = [c.lower() for c in choices]
        if len(lower) != len(set(lower)):
            errors.append(_err(row_num, "duplicate_choice", "choices are not unique case-insensitively"))

    return errors


def validate_authoring_csv_text(csv_text: str) -> dict:
    try:
        reader = csv.DictReader(io.StringIO(csv_text))
        # trigger parse to catch csv.Error early
        try:
            actual_columns = reader.fieldnames
        except csv.Error as exc:
            return {
                "ok": False,
                "rows_total": 0,
                "valid_rows": 0,
                "errors": [_err(0, "csv_parse_error", str(exc))],
            }

        if list(actual_columns or []) != EXPECTED_COLUMNS:
            return {
                "ok": False,
                "rows_total": 0,
                "valid_rows": 0,
                "errors": [_err(0, "bad_header",
                                f"expected {EXPECTED_COLUMNS}, got {list(actual_columns or [])}")],
            }

        all_errors: list[dict] = []
        rows_total = 0
        valid_rows = 0

        for row_num, row in enumerate(reader, start=1):
            rows_total += 1
            try:
                row_errors = _validate_row(row_num, row)
            except csv.Error as exc:
                row_errors = [_err(row_num, "csv_parse_error", str(exc))]
            if row_errors:
                all_errors.extend(row_errors)
            else:
                valid_rows += 1

    except csv.Error as exc:
        return {
            "ok": False,
            "rows_total": 0,
            "valid_rows": 0,
            "errors": [_err(0, "csv_parse_error", str(exc))],
        }

    return {
        "ok": len(all_errors) == 0,
        "rows_total": rows_total,
        "valid_rows": valid_rows,
        "errors": all_errors,
    }


def import_authoring_csv_text(
    conn: sqlite3.Connection,
    csv_text: str,
    *,
    dry_run: bool = True,
    author_user_id: int = 0,
) -> dict:
    validation = validate_authoring_csv_text(csv_text)

    if not validation["ok"] or dry_run:
        return {**validation, "import_count": 0}

    reader = csv.DictReader(io.StringIO(csv_text))
    import_count = 0

    for row in reader:
        distractors = [row[k].strip() for k in _DISTRACTOR_KEYS]
        correct = row["correct_choice"].strip()
        choices = [correct] + distractors

        payload = {
            "lemma":           row["lemma"].strip(),
            "pos":             row["pos"].strip(),
            "bin_name":        row["bin_name"].strip(),
            "prompt":          row["prompt"].strip(),
            "correct_choice":  correct,
            "distractors":     distractors,
            "choices":         choices,
            "source_note":     row["source_note"].strip(),
            "author_note":     row["author_note"].strip(),
            "author_user_id":  author_user_id,
        }

        conn.execute(
            """
            INSERT INTO vocab4_authoring_items
                (source_name, lemma, pos, bin_name, prompt, correct_choice,
                 distractors_json, payload_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["source_note"].strip(),
                row["lemma"].strip(),
                row["pos"].strip(),
                row["bin_name"].strip(),
                row["prompt"].strip(),
                correct,
                json.dumps(distractors),
                json.dumps(payload),
            ),
        )
        import_count += 1

    conn.commit()
    return {**validation, "import_count": import_count}
