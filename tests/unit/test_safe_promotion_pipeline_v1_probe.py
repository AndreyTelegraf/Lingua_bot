from pathlib import Path

def test_safe_promotion_probe_contains_batch_size() -> None:
    text = Path("tools/safe_promotion_pipeline_v1_probe.py").read_text(encoding="utf-8")
    assert "BATCH_SIZE = 50" in text
    assert "safe_promotion_batch_50.csv" in text
