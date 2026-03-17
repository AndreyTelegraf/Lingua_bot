from pathlib import Path

def test_activation_count_only_increments_on_real_activation_update() -> None:
    text = Path("services/vocab_bank/validate_items.py").read_text(encoding="utf-8")

    assert "cur = conn.execute(" in text
    assert "if cur.rowcount == 1:" in text
    assert "passed_count += 1" in text
