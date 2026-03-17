from pathlib import Path
import importlib.util


def test_orchestrator_module_loads() -> None:
    path = Path("tools/vocab_bank_orchestrator_dryrun.py")
    assert path.exists()
    spec = importlib.util.spec_from_file_location("vocab_bank_orchestrator_dryrun", path)
    assert spec is not None
    assert spec.loader is not None
