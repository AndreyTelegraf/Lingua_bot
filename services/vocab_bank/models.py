from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class RawEntryInput:
    source_name: str
    external_key: str | None
    raw_lemma: str | None
    raw_pos: str | None
    raw_level: str | None
    raw_freq: str | None
    raw_gloss_ru: str | None
    payload_json: str
