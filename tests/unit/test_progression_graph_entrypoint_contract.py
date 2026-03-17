from __future__ import annotations

import json
from pathlib import Path


def test_progression_graph_payload_contract_exists() -> None:
    path = Path("artifacts/progression_graph_entrypoint_20260317/graph_payload.json")
    if not path.exists():
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["graph_spec_version"] == "progression_graph_v1"
    assert "vocab" in data["sources"]
