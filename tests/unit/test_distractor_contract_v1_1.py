from pathlib import Path

def test_distractor_contract_v1_1_rules_present() -> None:
    text = Path("tools/apply_distractor_contract_v1_rebuild.py").read_text(encoding="utf-8")
    assert 'preferred_bins = {"2K", "5K"}' in text
    assert 'allowed_bins = {"2K", "5K", "10K"}' in text
    assert 'CLOSED_1K_NOUN_CLUSTER' in text
