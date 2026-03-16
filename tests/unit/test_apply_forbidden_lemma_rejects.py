from pathlib import Path

def test_apply_script_has_manual_keep_ids() -> None:
    text = Path("tools/apply_forbidden_lemma_rejects.py").read_text(encoding="utf-8")
    assert "MANUAL_KEEP_IDS = {1481, 1955}" in text
    assert "UPDATE vocab_items SET is_active = 0" in text
