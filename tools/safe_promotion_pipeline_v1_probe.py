from __future__ import annotations

import csv
import json
import sqlite3
from collections import Counter
from datetime import datetime, UTC
from pathlib import Path

BASE = Path("/home/andrey/Projects/lingua_bot_v2")
DB = BASE / "data" / "lingua_staging.db"
OUT_DIR = BASE / "artifacts" / f"safe_promotion_pipeline_v1_probe_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"
BATCH_SIZE = 50

def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    latest_probe = sorted(BASE.glob("artifacts/expansion_contract_v1_probe_*/expansion_contract_v1_promotable.csv"))[-1]
    rows = list(csv.DictReader(latest_probe.open(encoding="utf-8", newline="")))

    active_ids = {
        int(r["id"])
        for r in conn.execute("SELECT id FROM vocab_items WHERE is_active = 1").fetchall()
    }

    filtered = []
    for r in rows:
        item_id = int(r["id"])
        if item_id in active_ids:
            continue
        filtered.append(r)

    def sort_key(r: dict) -> tuple:
        try:
            freq = int(r.get("freq_rank") or 999999999)
        except Exception:
            freq = 999999999
        return (
            {"1K": 1, "2K": 2, "5K": 3, "10K": 4, "20K": 5}.get(r.get("bin_name") or "", 99),
            freq,
            int(r.get("id") or 0),
        )

    filtered.sort(key=sort_key)
    batch = filtered[:BATCH_SIZE]

    pos_counts = Counter(r.get("pos") or "UNKNOWN" for r in batch)
    bin_counts = Counter(r.get("bin_name") or "UNKNOWN" for r in batch)

    out_csv = OUT_DIR / "safe_promotion_batch_50.csv"
    with out_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(batch[0].keys()) if batch else [])
        writer.writeheader()
        writer.writerows(batch)

    summary = {
        "source_promotable_csv": str(latest_probe),
        "active_total_now": conn.execute("SELECT COUNT(*) FROM vocab_items WHERE is_active = 1").fetchone()[0],
        "remaining_promotable_not_active": len(filtered),
        "batch_size": len(batch),
        "batch_pos_counts": dict(pos_counts),
        "batch_bin_counts": dict(bin_counts),
        "output_dir": str(OUT_DIR),
    }

    (OUT_DIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    print("\n===== TOP 50 CANDIDATES =====")
    for i, r in enumerate(batch, 1):
        print(f"{i:02d}. id={r['id']} lemma={r['lemma']} pos={r['pos']} bin={r['bin_name']} freq={r['freq_rank']}")

    conn.close()

if __name__ == "__main__":
    main()
