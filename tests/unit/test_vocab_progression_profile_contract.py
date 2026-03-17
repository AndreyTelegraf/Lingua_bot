from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path("/home/andrey/Projects/lingua_bot_v2")
SCRIPT = ROOT / "tools" / "build_vocab_progression_profile_contract.py"
OUT = ROOT / "artifacts" / "vocab_progression_profile_contract_20260317" / "contract.json"


def test_vocab_progression_profile_contract_builds() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], check=True)
    assert OUT.exists()

    data = json.loads(OUT.read_text(encoding="utf-8"))

    assert "lexical_baseline" in data
    assert "lexical_profile" in data
    assert "progression_ready_hints" in data

    lp = data["lexical_profile"]
    assert "strongest_pos" in lp
    assert "strongest_cefr" in lp
    assert "strongest_concept_groups" in lp
