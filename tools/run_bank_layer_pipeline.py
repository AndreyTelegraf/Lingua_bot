from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.lib_bank_pipeline import LayerSpec, run_layer_pipeline


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--pos", required=True)
    p.add_argument("--bin", dest="bin_name", required=True)

    p.add_argument("--build-review-pack", action="store_true")
    p.add_argument("--cleanup-zero-choice-dups", action="store_true")
    p.add_argument("--build-priority-audit", action="store_true")
    p.add_argument("--apply-safe-fixes", action="store_true")
    p.add_argument("--purge-fully-inactive-dups", action="store_true")
    p.add_argument("--run-tests", action="store_true")
    p.add_argument("--restart-staging", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--full", action="store_true")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    if args.full:
        args.build_review_pack = True
        args.cleanup_zero_choice_dups = True
        args.build_priority_audit = True
        args.apply_safe_fixes = True

    spec = LayerSpec(pos=args.pos, bin_name=args.bin_name)

    result = run_layer_pipeline(
        spec,
        build_review_pack=args.build_review_pack,
        cleanup_zero_choice_dups=args.cleanup_zero_choice_dups,
        build_priority_audit=args.build_priority_audit,
        apply_safe_fixes=args.apply_safe_fixes,
        purge_fully_inactive_dups=args.purge_fully_inactive_dups,
        dry_run=args.dry_run,
    )

    print("===== UNIVERSAL BANK PIPELINE RESULT =====")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if args.run_tests:
        subprocess.run(". .venv/bin/activate && pytest -q", shell=True, check=True, executable="/bin/bash")

    if args.restart_staging:
        subprocess.run("sudo systemctl restart lingua-bot-staging.service", shell=True, check=True, executable="/bin/bash")
        subprocess.run("sleep 3", shell=True, check=True, executable="/bin/bash")
        subprocess.run(
            "sudo systemctl --no-pager --full status lingua-bot-staging.service | sed -n '1,80p'",
            shell=True,
            check=True,
            executable="/bin/bash",
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
