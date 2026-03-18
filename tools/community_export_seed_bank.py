#!/usr/bin/env python3
from __future__ import annotations

import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import get_settings
from services.community_block.bootstrap import bootstrap_community_layer
from services.community_block.content_registry import export_seed_bank


def main() -> None:
    settings = get_settings()
    db_path = Path(settings.db_path)

    out = ROOT / "artifacts" / f"community_seed_bank_{time.strftime('%Y%m%d_%H%M%S')}.jsonl"

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    bootstrap_community_layer(conn)
    path = export_seed_bank(conn, output_path=out)
    conn.close()

    print(path)


if __name__ == "__main__":
    main()
