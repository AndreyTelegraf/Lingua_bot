from pathlib import Path


def test_candidate_import_tool_exists() -> None:
    assert Path("tools/community_candidate_import.py").exists()


def test_export_seed_bank_tool_exists() -> None:
    assert Path("tools/community_export_seed_bank.py").exists()
