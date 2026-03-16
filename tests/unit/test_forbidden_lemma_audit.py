from pathlib import Path

def test_forbidden_lemma_audit_contract() -> None:
    text = Path("tools/forbidden_lemma_audit.py").read_text(encoding="utf-8")
    assert "PROPER_NAME_OR_TOPONYM" in text
    assert "FORBIDDEN_COGNATE" in text
    assert "forbidden_lemma_reject.csv" in text
