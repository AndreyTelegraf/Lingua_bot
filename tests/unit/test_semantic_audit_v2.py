from tools.semantic_audit_v2 import ItemRow, ChoiceRow, audit_item

def test_mixed_script_detected() -> None:
    item = ItemRow(1, "palavra", "словo", "noun", 1000, "A1", "2K")
    choices = [
        ChoiceRow(1, "palavra", 1, 0),
        ChoiceRow(1, "grupo", 0, 1),
        ChoiceRow(1, "empresa", 0, 2),
        ChoiceRow(1, "sociedade", 0, 3),
        ChoiceRow(1, "associação", 0, 4),
        ChoiceRow(1, "organização", 0, 5),
    ]
    active_meta = {
        "grupo": [{"id": 2, "lemma": "grupo", "pos": "noun", "freq_rank": 1010, "level": "A1", "bin_name": "2K"}],
        "empresa": [{"id": 3, "lemma": "empresa", "pos": "noun", "freq_rank": 1020, "level": "A1", "bin_name": "2K"}],
        "sociedade": [{"id": 4, "lemma": "sociedade", "pos": "noun", "freq_rank": 1030, "level": "A2", "bin_name": "5K"}],
        "associação": [{"id": 5, "lemma": "associação", "pos": "noun", "freq_rank": 1040, "level": "B1", "bin_name": "5K"}],
        "organização": [{"id": 6, "lemma": "organização", "pos": "noun", "freq_rank": 1050, "level": "B1", "bin_name": "5K"}],
    }
    row = audit_item(item, choices, active_meta, {"noun": {"median": 7, "p90": 12}})
    assert row["flag"] == "suspicious_translation"
    assert "gloss_mixed_script" in row["reasons"]

def test_valid_yo_not_flagged() -> None:
    item = ItemRow(1, "mel", "мёд", "noun", 1000, "A1", "2K")
    choices = [
        ChoiceRow(1, "mel", 1, 0),
        ChoiceRow(1, "grupo", 0, 1),
        ChoiceRow(1, "empresa", 0, 2),
        ChoiceRow(1, "sociedade", 0, 3),
        ChoiceRow(1, "associação", 0, 4),
        ChoiceRow(1, "organização", 0, 5),
    ]
    active_meta = {
        "grupo": [{"id": 2, "lemma": "grupo", "pos": "noun", "freq_rank": 1010, "level": "A1", "bin_name": "2K"}],
        "empresa": [{"id": 3, "lemma": "empresa", "pos": "noun", "freq_rank": 1020, "level": "A1", "bin_name": "2K"}],
        "sociedade": [{"id": 4, "lemma": "sociedade", "pos": "noun", "freq_rank": 1030, "level": "A2", "bin_name": "5K"}],
        "associação": [{"id": 5, "lemma": "associação", "pos": "noun", "freq_rank": 1040, "level": "B1", "bin_name": "5K"}],
        "organização": [{"id": 6, "lemma": "organização", "pos": "noun", "freq_rank": 1050, "level": "B1", "bin_name": "5K"}],
    }
    row = audit_item(item, choices, active_meta, {"noun": {"median": 7, "p90": 12}})
    assert row["flag"] == "clean_semantic_item"
