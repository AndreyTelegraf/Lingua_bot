from pathlib import Path

def test_apply_distractor_contract_v1_rebuild_contract() -> None:
    text = Path("tools/apply_distractor_contract_v1_rebuild.py").read_text(encoding="utf-8")
    assert "GENERIC_BAD" in text
    assert "distractor_contract_v1_rebuild.csv" in text
    assert "DELETE FROM vocab_choices WHERE item_id = ?" in text
