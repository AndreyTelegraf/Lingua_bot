from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path
from typing import Iterable

from services.vocab_bank.models import RawEntryInput


def _as_str_or_none(value: object) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


def _build_payload(record: dict[str, object]) -> str:
    return json.dumps(record, ensure_ascii=False, sort_keys=True)


def iter_csv_entries(path: Path, *, source_name: str) -> list[RawEntryInput]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        out: list[RawEntryInput] = []
        for row in reader:
            normalized = {str(k): v for k, v in row.items()}
            out.append(
                RawEntryInput(
                    source_name=source_name,
                    external_key=_as_str_or_none(normalized.get("external_key")),
                    raw_lemma=_as_str_or_none(normalized.get("lemma") or normalized.get("raw_lemma")),
                    raw_pos=_as_str_or_none(normalized.get("pos") or normalized.get("raw_pos")),
                    raw_level=_as_str_or_none(normalized.get("level") or normalized.get("raw_level")),
                    raw_freq=_as_str_or_none(normalized.get("freq") or normalized.get("raw_freq") or normalized.get("freq_rank")),
                    raw_gloss_ru=_as_str_or_none(normalized.get("ru_gloss") or normalized.get("raw_gloss_ru") or normalized.get("gloss_ru")),
                    payload_json=_build_payload(normalized),
                )
            )
    return out


def iter_jsonl_entries(path: Path, *, source_name: str) -> list[RawEntryInput]:
    out: list[RawEntryInput] = []
    with path.open("r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            raw = line.strip()
            if not raw:
                continue
            record = json.loads(raw)
            if not isinstance(record, dict):
                raise ValueError(f"jsonl_line_not_object:{line_no}")
            out.append(
                RawEntryInput(
                    source_name=source_name,
                    external_key=_as_str_or_none(record.get("external_key")),
                    raw_lemma=_as_str_or_none(record.get("lemma") or record.get("raw_lemma")),
                    raw_pos=_as_str_or_none(record.get("pos") or record.get("raw_pos")),
                    raw_level=_as_str_or_none(record.get("level") or record.get("raw_level")),
                    raw_freq=_as_str_or_none(record.get("freq") or record.get("raw_freq") or record.get("freq_rank")),
                    raw_gloss_ru=_as_str_or_none(record.get("ru_gloss") or record.get("raw_gloss_ru") or record.get("gloss_ru")),
                    payload_json=_build_payload(record),
                )
            )
    return out


def load_entries(path: Path, *, source_name: str, file_format: str) -> list[RawEntryInput]:
    fmt = file_format.strip().lower()
    if fmt == "csv":
        return iter_csv_entries(path, source_name=source_name)
    if fmt == "jsonl":
        return iter_jsonl_entries(path, source_name=source_name)
    raise ValueError(f"unsupported_format:{file_format}")


def ingest_entries(
    conn: sqlite3.Connection,
    *,
    entries: Iterable[RawEntryInput],
    truncate_source: bool = False,
) -> int:
    rows = list(entries)
    if not rows:
        return 0

    if truncate_source:
        source_names = sorted({row.source_name for row in rows})
        conn.executemany(
            "DELETE FROM vocab_raw_entries WHERE source_name = ?",
            [(name,) for name in source_names],
        )

    conn.executemany(
        """
        INSERT INTO vocab_raw_entries (
            source_name,
            external_key,
            raw_lemma,
            raw_pos,
            raw_level,
            raw_freq,
            raw_gloss_ru,
            payload_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                row.source_name,
                row.external_key,
                row.raw_lemma,
                row.raw_pos,
                row.raw_level,
                row.raw_freq,
                row.raw_gloss_ru,
                row.payload_json,
            )
            for row in rows
        ],
    )
    conn.commit()
    return len(rows)
