from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-jsonl", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()

    rows = []
    with args.input_jsonl.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))

    args.out_dir.mkdir(parents=True, exist_ok=True)
    out_tsv = args.out_dir / "community_review_pack_v1.tsv"
    out_json = args.out_dir / "community_review_pack_v1.json"

    with out_tsv.open("w", encoding="utf-8") as f:
        f.write("scenario_id\ttopic\tformat_type\topening_family\tcontext\tintent\treview_action\treview_note\ttext\n")
        for row in rows:
            vals = [
                row.get("scenario_id", ""),
                row.get("topic", ""),
                row.get("format_type", ""),
                row.get("opening_family", ""),
                row.get("context", ""),
                row.get("intent", ""),
                "keep",
                "",
                row.get("text", ""),
            ]
            f.write("\t".join(str(v).replace("\t", " ").replace("\n", " ") for v in vals) + "\n")

    out_json.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({
        "count": len(rows),
        "tsv": str(out_tsv),
        "json": str(out_json),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
