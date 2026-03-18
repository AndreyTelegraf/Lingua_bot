from pathlib import Path
import subprocess
import sys

ROOT = Path("/home/andrey/Projects/lingua_bot_v2")
TOOL = ROOT / "tools/vocab_noun_factory_v2.py"

def test_vocab_noun_factory_v2_compiles() -> None:
    subprocess.run([sys.executable, "-m", "py_compile", str(TOOL)], check=True)
