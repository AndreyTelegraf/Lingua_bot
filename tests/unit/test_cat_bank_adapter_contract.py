from __future__ import annotations

from services.cat_runtime import (
    CATItemModel,
    map_vocab_row_to_cat_item,
    map_vocab_rows_to_cat_items,
    summarize_vocab_rows_adapter,
)


def test_map_vocab_row_to_cat_item_preserves_core_fields() -> None:
    row = {
        "id": 101,
        "lemma": "casa",
        "question_text": "Choose the meaning of casa",
        "correct_answer": "house",
        "freq_rank": 120,
        "bin_name": "1K",
        "level": "A1",
        "topic_tag": "home",
        "pos": "noun",
        "is_active": 1,
    }

    item = map_vocab_row_to_cat_item(row)

    assert isinstance(item, CATItemModel)
    assert item.item_id == 101
    assert item.mode == "vocab"
    assert item.modality == "mcq"
    assert item.prompt_text == "Choose the meaning of casa"
    assert item.answer_key == "house"
    assert item.cefr_target == "A1"
    assert item.content_tag == "home"
    assert item.skill_tag == "noun"
    assert item.is_active is True


def test_map_vocab_row_to_cat_item_can_derive_difficulty_from_freq_rank() -> None:
    easy = map_vocab_row_to_cat_item(
        {
            "id": 1,
            "lemma": "vida",
            "question_text": "q1",
            "correct_answer": "a1",
            "freq_rank": 100,
            "is_active": 1,
        }
    )
    hard = map_vocab_row_to_cat_item(
        {
            "id": 2,
            "lemma": "heurística",
            "question_text": "q2",
            "correct_answer": "a2",
            "freq_rank": 15000,
            "is_active": 1,
        }
    )

    assert easy.difficulty_b < hard.difficulty_b


def test_map_vocab_row_to_cat_item_prefers_explicit_difficulty_when_present() -> None:
    row = {
        "id": 55,
        "lemma": "teste",
        "question_text": "q",
        "correct_answer": "a",
        "freq_rank": 100,
        "difficulty_b": 0.75,
        "is_active": 1,
    }

    item = map_vocab_row_to_cat_item(row)
    assert item.difficulty_b == 0.75


def test_map_vocab_rows_to_cat_items_skips_inactive_when_active_only() -> None:
    rows = [
        {"id": 1, "lemma": "a", "question_text": "q1", "correct_answer": "x", "is_active": 1},
        {"id": 2, "lemma": "b", "question_text": "q2", "correct_answer": "y", "is_active": 0},
        {"id": 3, "lemma": "c", "question_text": "q3", "correct_answer": "z", "is_active": 1},
    ]

    items = map_vocab_rows_to_cat_items(rows, active_only=True)
    assert [x.item_id for x in items] == [1, 3]


def test_summarize_vocab_rows_adapter_counts_total_mapped_and_skipped() -> None:
    rows = [
        {"id": 1, "question_text": "q1", "correct_answer": "a1", "is_active": 1},
        {"id": 2, "question_text": "q2", "correct_answer": "a2", "is_active": 0},
        {"id": 3, "question_text": "q3", "correct_answer": "a3", "is_active": 1},
    ]

    stats = summarize_vocab_rows_adapter(rows, active_only=True)
    assert stats.total_rows == 3
    assert stats.mapped_rows == 2
    assert stats.skipped_rows == 1
