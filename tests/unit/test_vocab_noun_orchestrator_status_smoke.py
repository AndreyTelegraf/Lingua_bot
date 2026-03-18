from pathlib import Path
import subprocess
import sys

ROOT = Path("/home/andrey/Projects/lingua_bot_v2")
TOOL = ROOT / "tools/vocab_noun_orchestrator_status.py"

def test_vocab_noun_orchestrator_status_compiles() -> None:
    subprocess.run([sys.executable, "-m", "py_compile", str(TOOL)], check=True)
