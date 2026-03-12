from __future__ import annotations

import os

import aiosqlite

from modes.vocab.repo import VocabRepository
from modes.vocab.state import SelectorRuntimeState

POS_TARGETS: dict[str, int] = {
    "noun": 8,
    "verb": 7,
    "adjective": 6,
    "adverb": 3,
}

CEFR_CAPS: dict[str, int] = {
    "A1": 6,
    "A2": 6,
    "B1": 6,
    "B2": 4,
    "C1": 2,
}

BIN_ORDER: list[str] = ["1K", "2K", "5K", "10K", "20K", "rare"]


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


class VocabSelector:
    def __init__(self, conn: aiosqlite.Connection) -> None:
        self.conn = conn
        self.repo = VocabRepository(conn)
        self.max_global_shown = _env_int("VOCAB_SELECTOR_MAX_ITEM_SHOWN_GLOBAL", 0)
        self.item_cooldown_sec = _env_int("VOCAB_SELECTOR_ITEM_COOLDOWN_SEC", 0)

    def _underused_bins_order(self, state: SelectorRuntimeState) -> list[str]:
        scored: list[tuple[int, int, str]] = []
        for idx, bin_name in enumerate(BIN_ORDER):
            actual = state.bin_counters.get(bin_name, 0)
            scored.append((actual, idx, bin_name))
        scored.sort(key=lambda x: (x[0], x[1]))
        return [x[2] for x in scored]

    def _eligible_cefr_levels(self, state: SelectorRuntimeState) -> list[str]:
        eligible: list[str] = []
        for level in ["A1", "A2", "B1", "B2", "C1"]:
            if state.cefr_counters.get(level, 0) < CEFR_CAPS[level]:
                eligible.append(level)
        return eligible

    async def _fetch_candidates(
        self,
        *,
        excluded_ids: list[int],
        apply_cooldown: bool,
    ) -> list[aiosqlite.Row]:
        base_sql = """
        WITH ready_items AS (
            SELECT vc.item_id
            FROM vocab_choices vc
            GROUP BY vc.item_id
            HAVING COUNT(*) = 6
        ),
        bin_exposure AS (
            SELECT
                vi2.bin_name AS bin_name,
                AVG(COALESCE(vie2.shown_count, 0)) AS bin_avg_shown
            FROM vocab_items vi2
            LEFT JOIN vocab_item_exposure vie2 ON vie2.item_id = vi2.id
            WHERE vi2.is_active = 1
            GROUP BY vi2.bin_name
        )
        SELECT
            vi.id,
            vi.lemma,
            vi.question_text,
            vi.correct_answer,
            vi.pos,
            vi.level,
            vi.bin_name,
            vi.freq_rank,
            COALESCE(vie.shown_count, 0) AS global_shown_count,
            vie.last_shown_at AS last_shown_at,
            COALESCE(be.bin_avg_shown, 0.0) AS bin_avg_shown
        FROM vocab_items vi
        INNER JOIN ready_items ri ON ri.item_id = vi.id
        LEFT JOIN vocab_item_exposure vie ON vie.item_id = vi.id
        LEFT JOIN bin_exposure be ON be.bin_name = vi.bin_name
        WHERE vi.is_active = 1
        """

        params_list: list[object] = []
        sql = base_sql

        if excluded_ids:
            placeholders = ",".join("?" for _ in excluded_ids)
            sql += f"\n  AND vi.id NOT IN ({placeholders})"
            params_list.extend(excluded_ids)

        if self.max_global_shown > 0:
            sql += "\n  AND COALESCE(vie.shown_count, 0) < ?"
            params_list.append(self.max_global_shown)

        if apply_cooldown and self.item_cooldown_sec > 0:
            sql += """
  AND (
        vie.last_shown_at IS NULL
        OR ((julianday('now') - julianday(vie.last_shown_at)) * 86400.0) >= ?
      )
"""
            params_list.append(self.item_cooldown_sec)

        cursor = await self.conn.execute(sql, tuple(params_list))
        rows = await cursor.fetchall()
        return list(rows)

    def _candidate_sort_key(
        self,
        row: aiosqlite.Row,
        *,
        state: SelectorRuntimeState,
        preferred_bins: list[str],
    ) -> tuple[float, int, int, float, int, int, int]:
        pos = row["pos"]
        pos_str = str(pos) if pos is not None else ""
        target = POS_TARGETS.get(pos_str, 999999)
        actual = state.pos_counters.get(pos_str, 0)

        if pos_str in POS_TARGETS and target > 0:
            pos_ratio = actual / target
            pos_actual = actual
        else:
            pos_ratio = 999999.0
            pos_actual = 999999

        global_shown_count = int(row["global_shown_count"]) if row["global_shown_count"] is not None else 0
        bin_avg_shown = float(row["bin_avg_shown"]) if row["bin_avg_shown"] is not None else 0.0

        bin_rank_map = {name: idx for idx, name in enumerate(preferred_bins)}
        row_bin = row["bin_name"]
        if row_bin is None:
            bin_rank = 999999
        else:
            bin_rank = bin_rank_map.get(str(row_bin), 999998)

        row_rank = row["freq_rank"]
        if row_rank is None:
            freq_rank = 999999999
        else:
            freq_rank = int(row_rank)

        return (
            pos_ratio,
            pos_actual,
            global_shown_count,
            bin_avg_shown,
            bin_rank,
            freq_rank,
            int(row["id"]),
        )

    def _sort_candidates(
        self,
        rows: list[aiosqlite.Row],
        *,
        state: SelectorRuntimeState,
        preferred_bins: list[str],
    ) -> list[aiosqlite.Row]:
        return sorted(
            rows,
            key=lambda row: self._candidate_sort_key(
                row,
                state=state,
                preferred_bins=preferred_bins,
            ),
        )

    def _filter_ideal(
        self,
        rows: list[aiosqlite.Row],
        *,
        eligible_levels: list[str],
    ) -> list[aiosqlite.Row]:
        out: list[aiosqlite.Row] = []
        for row in rows:
            if row["level"] is not None and str(row["level"]) not in eligible_levels:
                continue
            out.append(row)
        return out

    def _filter_cefr_relaxed(self, rows: list[aiosqlite.Row]) -> list[aiosqlite.Row]:
        return list(rows)

    async def _pick_from_rows(
        self,
        *,
        rows: list[aiosqlite.Row],
        state: SelectorRuntimeState,
    ) -> aiosqlite.Row | None:
        if not rows:
            return None

        eligible_levels = self._eligible_cefr_levels(state)
        preferred_bins = self._underused_bins_order(state)

        ideal = self._filter_ideal(
            rows,
            eligible_levels=eligible_levels,
        )
        if ideal:
            return self._sort_candidates(
                ideal,
                state=state,
                preferred_bins=preferred_bins,
            )[0]

        cefr_relaxed = self._filter_cefr_relaxed(rows)
        if cefr_relaxed:
            return self._sort_candidates(
                cefr_relaxed,
                state=state,
                preferred_bins=preferred_bins,
            )[0]

        return None

    async def pick_next_item(self, *, attempt_id: int) -> aiosqlite.Row | None:
        state = await self.repo.get_selector_state(attempt_id=attempt_id)

        strict_rows = await self._fetch_candidates(
            excluded_ids=state.shown_item_ids[:],
            apply_cooldown=True,
        )
        picked = await self._pick_from_rows(rows=strict_rows, state=state)
        if picked is not None:
            return picked

        relaxed_rows = await self._fetch_candidates(
            excluded_ids=state.shown_item_ids[:],
            apply_cooldown=False,
        )
        return await self._pick_from_rows(rows=relaxed_rows, state=state)
