from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path("/home/andrey/Projects/lingua_bot_v2")
SCRIPT = ROOT / "tools" / "build_vocab_progression_reader_v1.py"
OUT = ROOT / "artifacts" / "vocab_progression_reader_v1_20260317" / "profile.json"

def test_vocab_progression_reader_v1_builds_profile() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], check=True)
    assert OUT.exists()

    data = json.loads(OUT.read_text(encoding="utf-8"))
    assert "lexical_baseline" in data
    assert "lexical_profile" in data
    assert "progression_ready_hints" in data
    assert "observed_attempt_profile" in data
    assert "bank_baseline_profile" in data
    assert "signal_quality" in data

    lp = data["lexical_profile"]
    assert "strongest_pos" in lp
    assert "weakest_pos" in lp
    assert "weak_lemmas_sample" in lp

def test_vocab_progression_reader_v1_suppresses_single_pos_noise() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], check=True)
    data = json.loads(OUT.read_text(encoding="utf-8"))
    sq = data["signal_quality"]
    lp = data["lexical_profile"]

    if sq["single_pos_attempt"]:
        assert lp["strongest_pos"] == []
        assert lp["weakest_pos"] == []

def test_vocab_progression_reader_v1_only_recommends_supported_groups() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], check=True)
    data = json.loads(OUT.read_text(encoding="utf-8"))
    hints = data["progression_ready_hints"]
    for key in hints["recommended_lesson_packs"]:
        assert isinstance(key, str) and key.strip()
