from __future__ import annotations

import json
from dataclasses import dataclass


KNOWN_POS: list[str] = ["noun", "verb", "adjective", "adverb"]
KNOWN_BINS: list[str] = ["1K", "2K", "5K", "10K", "20K"]

DEFAULT_POS_QUOTA: dict[str, int] = {
    "noun": 10,
    "verb": 5,
    "adjective": 5,
    "adverb": 4,
}

DEFAULT_BIN_QUOTA: dict[str, int] = {
    "1K": 8,
    "2K": 7,
    "5K": 6,
    "10K": 3,
    "20K": 0,
}


@dataclass
class SelectorState:
    pos_quota: dict[str, int]
    pos_used: dict[str, int]
    bin_quota: dict[str, int]
    bin_used: dict[str, int]
    shown_item_ids: list[int]

    @classmethod
    def initial(
        cls,
        pos_quota: dict[str, int] | None = None,
        bin_quota: dict[str, int] | None = None,
    ) -> SelectorState:
        pq = dict(pos_quota) if pos_quota is not None else dict(DEFAULT_POS_QUOTA)
        bq = dict(bin_quota) if bin_quota is not None else dict(DEFAULT_BIN_QUOTA)
        return cls(
            pos_quota=pq,
            pos_used={pos: 0 for pos in pq},
            bin_quota=bq,
            bin_used={b: 0 for b in bq},
            shown_item_ids=[],
        )

    def to_json(self) -> str:
        return json.dumps(
            {
                "pos_quota": self.pos_quota,
                "pos_used": self.pos_used,
                "bin_quota": self.bin_quota,
                "bin_used": self.bin_used,
                "shown_item_ids": self.shown_item_ids,
            },
            separators=(",", ":"),
        )

    @classmethod
    def from_json(cls, s: str) -> SelectorState:
        d = json.loads(s)
        required = {"pos_quota", "pos_used", "bin_quota", "bin_used", "shown_item_ids"}
        missing = required - d.keys()
        if missing:
            raise ValueError(f"SelectorState JSON missing keys: {missing}")
        return cls(
            pos_quota=d["pos_quota"],
            pos_used=d["pos_used"],
            bin_quota=d["bin_quota"],
            bin_used=d["bin_used"],
            shown_item_ids=d["shown_item_ids"],
        )
