from services.cat_runtime.estimator import (
    CATResponse,
    build_cat_responses,
    estimate_theta_map,
)
from services.cat_runtime.item_model import CATItemModel


def test_cat_estimator_empty_uses_prior() -> None:
    est = estimate_theta_map([])
    assert round(est.theta, 6) == 0.0
    assert est.items_answered == 0
    assert est.converged is True
    assert est.se > 0


def test_cat_estimator_more_correct_means_higher_theta() -> None:
    weak = [
        CATResponse(item_id=1, score=0, difficulty_b=-0.5),
        CATResponse(item_id=2, score=0, difficulty_b=0.0),
        CATResponse(item_id=3, score=1, difficulty_b=-1.0),
    ]
    strong = [
        CATResponse(item_id=1, score=1, difficulty_b=-0.5),
        CATResponse(item_id=2, score=1, difficulty_b=0.0),
        CATResponse(item_id=3, score=1, difficulty_b=0.8),
    ]
    est_weak = estimate_theta_map(weak)
    est_strong = estimate_theta_map(strong)
    assert est_strong.theta > est_weak.theta


def test_cat_estimator_harder_correct_items_raise_theta() -> None:
    easy = [
        CATResponse(item_id=1, score=1, difficulty_b=-1.5),
        CATResponse(item_id=2, score=1, difficulty_b=-1.0),
        CATResponse(item_id=3, score=1, difficulty_b=-0.5),
    ]
    hard = [
        CATResponse(item_id=1, score=1, difficulty_b=0.5),
        CATResponse(item_id=2, score=1, difficulty_b=1.0),
        CATResponse(item_id=3, score=1, difficulty_b=1.5),
    ]
    est_easy = estimate_theta_map(easy)
    est_hard = estimate_theta_map(hard)
    assert est_hard.theta > est_easy.theta


def test_cat_estimator_more_items_reduce_se() -> None:
    short = build_cat_responses([
        (1, 1, 0.0, 1.0),
        (2, 0, 0.5, 1.0),
    ])
    long = build_cat_responses([
        (1, 1, 0.0, 1.0),
        (2, 0, 0.5, 1.0),
        (3, 1, 0.3, 1.0),
        (4, 0, 0.8, 1.0),
        (5, 1, 0.1, 1.0),
        (6, 0, 0.6, 1.0),
    ])
    est_short = estimate_theta_map(short)
    est_long = estimate_theta_map(long)
    assert est_long.se < est_short.se


def test_cat_estimator_from_item_models_smoke() -> None:
    items = [
        CATItemModel(
            item_id=1,
            mode="level_cat",
            modality="mcq",
            prompt_text="a",
            answer_key="x",
            difficulty_b=-0.2,
            discrimination_a=1.1,
        ),
        CATItemModel(
            item_id=2,
            mode="level_cat",
            modality="mcq",
            prompt_text="b",
            answer_key="y",
            difficulty_b=0.6,
            discrimination_a=1.2,
        ),
    ]
    est = estimate_theta_map([
        CATResponse(item_id=items[0].item_id, score=1, difficulty_b=items[0].difficulty_b, discrimination_a=items[0].discrimination_a),
        CATResponse(item_id=items[1].item_id, score=0, difficulty_b=items[1].difficulty_b, discrimination_a=items[1].discrimination_a),
    ])
    assert est.items_answered == 2
    assert -4.0 <= est.theta <= 4.0
    assert est.se > 0
