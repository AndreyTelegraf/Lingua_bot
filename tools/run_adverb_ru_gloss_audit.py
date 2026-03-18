from __future__ import annotations

import argparse
import json

from services.vocab_qa.adverb_gloss_audit import run_adverb_audit


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--artifacts-dir", default="artifacts")
    args = ap.parse_args()

    summary = run_adverb_audit(args.db, args.artifacts_dir)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
