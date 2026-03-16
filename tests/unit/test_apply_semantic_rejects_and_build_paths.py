from pathlib import Path

def test_log_paths_use_out_dir() -> None:
    base = Path("/repo")
    out_dir = base / "artifacts" / "semantic_apply_and_build_20260315_204012"
    assert (out_dir / "build_apply_stdout.log") == Path("/repo/artifacts/semantic_apply_and_build_20260315_204012/build_apply_stdout.log")
    assert (out_dir / "build_apply_stderr.log") == Path("/repo/artifacts/semantic_apply_and_build_20260315_204012/build_apply_stderr.log")
