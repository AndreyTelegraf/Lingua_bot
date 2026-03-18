from pathlib import Path
import subprocess
import sys

ROOT = Path("/home/andrey/Projects/lingua_bot_v2")
TOOL = ROOT / "tools/vocab_noun_remediation_apply_v5.py"

def test_vocab_noun_remediation_apply_v5_compiles() -> None:
    subprocess.run([sys.executable, "-m", "py_compile", str(TOOL)], check=True)
