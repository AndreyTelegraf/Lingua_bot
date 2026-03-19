import importlib.util
import sys
from pathlib import Path
import tempfile
import os

ROOT = Path("/home/andrey/Projects/lingua_bot_v2")
MOD_PATH = ROOT / "tools" / "community_post_once.py"

spec = importlib.util.spec_from_file_location("community_post_once", MOD_PATH)
assert spec is not None and spec.loader is not None
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


class DummySettings:
    db_path = "/default/db.sqlite"


def test_resolve_db_path_prefers_explicit():
    s = DummySettings()
    assert mod.resolve_db_path("/explicit/staging.db", s) == "/explicit/staging.db"
    assert mod.resolve_db_path(None, s) == "/default/db.sqlite"


def test_load_env_file_sets_variables():
    with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as f:
        f.write("# comment\n")
        f.write("FEATURE_COMMUNITY_ENABLED=1\n")
        f.write("COMMUNITY_DRY_RUN=0\n")
        path = f.name
    try:
        os.environ.pop("FEATURE_COMMUNITY_ENABLED", None)
        os.environ.pop("COMMUNITY_DRY_RUN", None)
        mod.load_env_file(path)
        assert os.environ["FEATURE_COMMUNITY_ENABLED"] == "1"
        assert os.environ["COMMUNITY_DRY_RUN"] == "0"
    finally:
        Path(path).unlink(missing_ok=True)
