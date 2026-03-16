from pathlib import Path

def test_probe_has_expected_outputs() -> None:
    text = Path("tools/post_promotion_audit_v1_probe.py").read_text(encoding="utf-8")
    assert "post_promotion_audit_v1.csv" in text
    assert "safe_batch50_v1_3" in text
    assert "review6_keep" in text
