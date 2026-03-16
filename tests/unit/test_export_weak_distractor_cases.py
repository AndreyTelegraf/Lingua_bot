from pathlib import Path

def test_export_script_has_expected_contract() -> None:
    text = Path("tools/export_weak_distractor_cases.py").read_text(encoding="utf-8")
    assert "BAD_DISTRACTOR_SHAPE" in text
    assert "TARGET_COGNATE_TRANSPARENT" in text
    assert "weak_distractor_rebuild.csv" in text
