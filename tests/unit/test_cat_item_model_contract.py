from services.cat_runtime.item_model import CATItemModel, validate_cat_item_model


def test_cat_item_model_valid_smoke() -> None:
    item = CATItemModel(
        item_id=1,
        mode="level_cat",
        modality="mcq",
        prompt_text="Escolha a opção correta.",
        answer_key="B",
        difficulty_b=0.0,
        discrimination_a=1.2,
        guessing_c=0.2,
        upper_d=1.0,
        cefr_target="A2",
        content_tag="daily_life",
        skill_tag="grammar",
        is_active=True,
        exposure_max_rate=0.2,
    )
    assert validate_cat_item_model(item) == []


def test_cat_item_model_rejects_bad_ranges() -> None:
    item = CATItemModel(
        item_id=0,
        mode="",
        modality="unknown",
        prompt_text="",
        answer_key="",
        difficulty_b=9.0,
        discrimination_a=0.0,
        guessing_c=1.0,
        upper_d=0.0,
        cefr_target="Z9",
        exposure_max_rate=1.5,
    )
    errors = validate_cat_item_model(item)
    assert "item_id must be positive" in errors
    assert "mode must be non-empty" in errors
    assert "unsupported modality: unknown" in errors
    assert "prompt_text must be non-empty" in errors
    assert "answer_key must be non-empty" in errors
    assert "difficulty_b must be within [-6, 6]" in errors
    assert "discrimination_a must be > 0" in errors
    assert "guessing_c must be within [0, 1)" in errors
    assert "upper_d must be within (0, 1]" in errors
    assert "unsupported cefr_target: Z9" in errors
    assert "exposure_max_rate must be within (0, 1]" in errors


def test_cat_item_model_rejects_c_ge_d() -> None:
    item = CATItemModel(
        item_id=7,
        mode="level_cat",
        modality="mcq",
        prompt_text="x",
        answer_key="y",
        difficulty_b=0.0,
        discrimination_a=1.0,
        guessing_c=0.4,
        upper_d=0.4,
    )
    errors = validate_cat_item_model(item)
    assert "guessing_c must be less than upper_d" in errors
