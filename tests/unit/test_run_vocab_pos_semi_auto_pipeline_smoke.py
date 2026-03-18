from pathlib import Path

def test_unified_pipeline_module_exists():
    path = Path("tools/run_vocab_pos_semi_auto_pipeline.py")
    assert path.exists()
