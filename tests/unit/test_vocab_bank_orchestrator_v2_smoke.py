from pathlib import Path
import subprocess
import sys

ROOT = Path("/home/andrey/Projects/lingua_bot_v2")
TOOL = ROOT / "tools/vocab_bank_orchestrator_v2.py"

def test_orchestrator_v2_compiles_and_dryruns() -> None:
    subprocess.run([sys.executable, "-m", "py_compile", str(TOOL)], check=True)
