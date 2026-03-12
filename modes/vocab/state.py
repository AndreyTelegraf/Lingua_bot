from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class SelectorRuntimeState:
    shown_item_ids: list[int] = field(default_factory=list)
    pos_counters: dict[str, int] = field(default_factory=dict)
    cefr_counters: dict[str, int] = field(default_factory=dict)
    bin_counters: dict[str, int] = field(default_factory=dict)
    current_item_meta: dict[str, object] = field(default_factory=dict)

    def mark_item_shown(
        self,
        *,
        item_id: int,
        pos: str | None,
        level: str | None,
        bin_name: str | None,
        step_index: int,
    ) -> None:
        if item_id not in self.shown_item_ids:
            self.shown_item_ids.append(item_id)

        if pos:
            self.pos_counters[pos] = self.pos_counters.get(pos, 0) + 1
        if level:
            self.cefr_counters[level] = self.cefr_counters.get(level, 0) + 1
        if bin_name:
            self.bin_counters[bin_name] = self.bin_counters.get(bin_name, 0) + 1

        self.current_item_meta = {
            "item_id": item_id,
            "pos": pos,
            "level": level,
            "bin_name": bin_name,
            "step_index": step_index,
        }

    def clear_current_item(self) -> None:
        self.current_item_meta = {}
