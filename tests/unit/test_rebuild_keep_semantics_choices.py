from pathlib import Path

def test_targets_present() -> None:
    text = Path("tools/rebuild_keep_semantics_choices.py").read_text(encoding="utf-8")
    assert "TARGET_IDS = [163, 566]" in text
    assert "DELETE FROM vocab_choices WHERE item_id = ?" in text
    assert "INSERT INTO vocab_choices" in text
