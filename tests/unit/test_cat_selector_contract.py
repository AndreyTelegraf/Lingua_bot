from services.cat_runtime.item_model import CATItemModel
from services.cat_runtime.selector import (
    item_information,
    rank_candidates_for_theta,
    select_next_item_for_theta,
)


def _item(
    item_id: int,
    difficulty_b: float,
    discrimination_a: float = 1.0,
) -> CATItemModel:
    return CATItemModel(
        item_id=item_id,
        mode="level_cat",
        modality="mcq",
        prompt_text=f"prompt {item_id}",
        answer_key=f"answer {item_id}",
        difficulty_b=difficulty_b,
        discrimination_a=discrimination_a,
    )


def test_item_information_peaks_near_item_difficulty() -> None:
    item = _item(1, difficulty_b=0.5, discrimination_a=1.0)
    near = item_information(item, theta=0.5)
    far = item_information(item, theta=2.5)
    assert near > far


def test_higher_discrimination_increases_information_near_theta() -> None:
    low = _item(1, difficulty_b=0.0, discrimination_a=0.8)
    high = _item(2, difficulty_b=0.0, discrimination_a=1.6)
    assert item_information(high, theta=0.0) > item_information(low, theta=0.0)


def test_rank_candidates_prefers_closer_item_to_theta_when_discrimination_same() -> None:
    items = [
        _item(1, difficulty_b=-1.0, discrimination_a=1.0),
        _item(2, difficulty_b=0.1, discrimination_a=1.0),
        _item(3, difficulty_b=1.3, discrimination_a=1.0),
    ]
    ranked = rank_candidates_for_theta(items, theta=0.0)
    assert [x.item_id for x in ranked][:2] == [2, 1]


def test_rank_candidates_respects_exclusions() -> None:
    items = [
        _item(1, difficulty_b=0.0),
        _item(2, difficulty_b=0.1),
        _item(3, difficulty_b=0.2),
    ]
    ranked = rank_candidates_for_theta(items, theta=0.0, exclude_item_ids={1, 2})
    assert [x.item_id for x in ranked] == [3]


def test_select_next_item_returns_most_informative_item() -> None:
    items = [
        _item(11, difficulty_b=-1.5),
        _item(12, difficulty_b=0.2),
        _item(13, difficulty_b=1.1),
    ]
    picked = select_next_item_for_theta(items, theta=0.0)
    assert picked is not None
    assert picked.item_id == 12


def test_select_next_item_returns_none_when_all_excluded() -> None:
    items = [
        _item(21, difficulty_b=0.0),
        _item(22, difficulty_b=0.3),
    ]
    picked = select_next_item_for_theta(items, theta=0.0, exclude_item_ids={21, 22})
    assert picked is None
