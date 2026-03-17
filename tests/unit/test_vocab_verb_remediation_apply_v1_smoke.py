from pathlib import Path
import importlib.util

def test_verb_remediation_apply_module_loads() -> None:
    path = Path("tools/vocab_verb_remediation_apply_v1.py")
    assert path.exists()
    spec = importlib.util.spec_from_file_location("vocab_verb_remediation_apply_v1", path)
    assert spec is not None
    assert spec.loader is not None
