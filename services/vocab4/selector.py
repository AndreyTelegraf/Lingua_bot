from __future__ import annotations

from .attempt_state import KNOWN_BINS, KNOWN_POS, SelectorState
from .exceptions import InsufficientBankError

_BIN_ORDER: dict[str, int] = {b: i for i, b in enumerate(KNOWN_BINS)}
_POS_ORDER: dict[str, int] = {p: i for i, p in enumerate(KNOWN_POS)}


def select_next(
    pool: list[dict],
    state: SelectorState,
) -> tuple[dict, SelectorState]:
    """Return (selected_item, new_state). Never mutates state."""
    if not pool:
        raise InsufficientBankError("pool is empty")

    # --- step 1: pick POS with highest positive deficit ---
    best_pos: str | None = None
    best_deficit = 0
    for pos in KNOWN_POS:
        deficit = state.pos_quota.get(pos, 0) - state.pos_used.get(pos, 0)
        if deficit > best_deficit:
            best_deficit = deficit
            best_pos = pos

    if best_pos is None:
        raise InsufficientBankError("all pos quotas exhausted")

    # --- step 2: filter pool to target POS, exclude shown ---
    candidates = [
        item for item in pool
        if item["pos"] == best_pos and item["id"] not in state.shown_item_ids
    ]
    if not candidates:
        raise InsufficientBankError(
            f"no certified items available for pos={best_pos!r}"
        )

    # --- step 3: pick bin by highest positive deficit; fallback to least-used ---
    available_bins: set[str] = {item["bin_name"] for item in candidates}

    bin_deficits: dict[str, int] = {
        b: state.bin_quota.get(b, 0) - state.bin_used.get(b, 0)
        for b in available_bins
    }

    max_positive = max((d for d in bin_deficits.values() if d > 0), default=None)

    if max_positive is not None:
        target_bin = min(
            (b for b, d in bin_deficits.items() if d == max_positive),
            key=lambda b: _BIN_ORDER.get(b, 999),
        )
    else:
        min_used = min(state.bin_used.get(b, 0) for b in available_bins)
        target_bin = min(
            (b for b in available_bins if state.bin_used.get(b, 0) == min_used),
            key=lambda b: _BIN_ORDER.get(b, 999),
        )

    # --- step 4: sort within bin by freq_rank ASC, id ASC ---
    bin_candidates = [item for item in candidates if item["bin_name"] == target_bin]
    bin_candidates.sort(key=lambda item: (item.get("freq_rank") or 999_999, item["id"]))
    selected = bin_candidates[0]

    # --- step 5: build new state without mutating original ---
    new_state = SelectorState(
        pos_quota=dict(state.pos_quota),
        pos_used=dict(state.pos_used),
        bin_quota=dict(state.bin_quota),
        bin_used=dict(state.bin_used),
        shown_item_ids=list(state.shown_item_ids),
    )
    new_state.pos_used[selected["pos"]] = new_state.pos_used.get(selected["pos"], 0) + 1
    new_state.bin_used[selected["bin_name"]] = new_state.bin_used.get(selected["bin_name"], 0) + 1
    new_state.shown_item_ids.append(selected["id"])

    return selected, new_state
