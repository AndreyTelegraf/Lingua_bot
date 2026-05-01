from __future__ import annotations

import pytest

from services.vocab4.attempt_state import DEFAULT_BIN_QUOTA, DEFAULT_POS_QUOTA, SelectorState
from services.vocab4.exceptions import InsufficientBankError
from services.vocab4.selector import select_next


def _item(
    id: int,
    pos: str,
    bin_name: str,
    freq_rank: int | None = None,
) -> dict:
    return {"id": id, "pos": pos, "bin_name": bin_name, "freq_rank": freq_rank}


# --- test 1 ---

def test_initial_state_has_correct_shape() -> None:
    state = SelectorState.initial()
    assert state.pos_quota == {"noun": 10, "verb": 5, "adjective": 5, "adverb": 4}
    assert state.pos_used == {"noun": 0, "verb": 0, "adjective": 0, "adverb": 0}
    assert state.bin_quota == {"1K": 8, "2K": 7, "5K": 6, "10K": 3, "20K": 0}
    assert state.bin_used == {"1K": 0, "2K": 0, "5K": 0, "10K": 0, "20K": 0}
    assert state.shown_item_ids == []


# --- test 2 ---

def test_state_roundtrip_json() -> None:
    state = SelectorState.initial()
    state.pos_used["noun"] = 3
    state.bin_used["2K"] = 2
    state.shown_item_ids = [10, 20, 30]
    restored = SelectorState.from_json(state.to_json())
    assert restored == state


# --- test 3 ---

def test_selects_highest_pos_deficit_first() -> None:
    pool = [_item(1, "noun", "1K"), _item(2, "verb", "1K")]
    state = SelectorState.initial()
    item, _ = select_next(pool, state)
    assert item["pos"] == "noun"


# --- test 4 ---

def test_selected_item_added_to_shown_and_counters_updated() -> None:
    pool = [_item(7, "noun", "2K", freq_rank=500)]
    state = SelectorState.initial()
    item, new_state = select_next(pool, state)
    assert item["id"] == 7
    assert 7 in new_state.shown_item_ids
    assert new_state.pos_used["noun"] == 1
    assert new_state.bin_used["2K"] == 1
    assert state.pos_used["noun"] == 0


# --- test 5 ---

def test_no_duplicate_selection() -> None:
    pool = [_item(1, "noun", "1K")]
    state = SelectorState.initial()
    _, state2 = select_next(pool, state)
    with pytest.raises(InsufficientBankError):
        select_next(pool, state2)


# --- test 6 ---

def test_fail_closed_empty_pool() -> None:
    state = SelectorState.initial()
    with pytest.raises(InsufficientBankError):
        select_next([], state)


# --- test 7 ---

def test_fail_closed_pos_quota_exhausted() -> None:
    pool = [_item(i, "noun", "1K") for i in range(1, 5)]
    state = SelectorState.initial(
        pos_quota={"noun": 0, "verb": 0, "adjective": 0, "adverb": 0}
    )
    with pytest.raises(InsufficientBankError):
        select_next(pool, state)


# --- test 8 ---

def test_bin_deficit_tiebreak() -> None:
    # fresh state: 1K deficit=8, 2K deficit=7 → 1K has higher positive deficit
    pool = [_item(1, "noun", "2K"), _item(2, "noun", "1K")]
    state = SelectorState.initial()
    item, _ = select_next(pool, state)
    assert item["bin_name"] == "1K"


# --- test 9 (new) ---

def test_initial_state_includes_bin_quota() -> None:
    state = SelectorState.initial()
    assert hasattr(state, "bin_quota")
    assert set(state.bin_quota.keys()) == {"1K", "2K", "5K", "10K", "20K"}
    assert state.bin_quota["20K"] == 0
    assert state.bin_quota["1K"] == 8
    assert state.bin_quota["10K"] == 3


# --- test 10 (new) ---

def test_state_json_roundtrip_preserves_bin_quota() -> None:
    state = SelectorState.initial()
    state.bin_quota["1K"] = 99
    state.bin_used["1K"] = 5
    restored = SelectorState.from_json(state.to_json())
    assert restored.bin_quota == state.bin_quota
    assert restored.bin_used == state.bin_used


# --- test 11 (new) ---

def test_bin_quota_deficit_beats_least_used() -> None:
    # 1K: bin_used=3, bin_quota=8 → deficit=5 (positive)
    # 20K: bin_used=0, bin_quota=0 → deficit=0 (not positive)
    # 1K must win even though it has higher bin_used
    pool = [_item(1, "noun", "20K"), _item(2, "noun", "1K")]
    state = SelectorState.initial()
    state.bin_used["1K"] = 3
    item, _ = select_next(pool, state)
    assert item["bin_name"] == "1K"


# --- test 12 (new) ---

def test_20k_not_preferred_while_positive_deficit_exists() -> None:
    # fresh state: 1K quota=8 (deficit=8), 20K quota=0 (deficit=0)
    # 20K is in pool but must not be selected
    pool = [_item(1, "noun", "20K"), _item(2, "noun", "1K")]
    state = SelectorState.initial()
    item, _ = select_next(pool, state)
    assert item["bin_name"] == "1K"
