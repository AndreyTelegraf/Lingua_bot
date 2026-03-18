from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

ROOT = Path("/home/andrey/Projects/lingua_bot_v2")
ART = ROOT / "artifacts"

PREFER = {
    "vista", "quarto",
}

BLOCKED_LEMMAS = {
    "essa","além","nosso","toda","for","quase","tanto","fora","brasileira","nossos","tal",
    "veja","olha","entanto","principal","livre","teu","próximo","obrigado","baixo","chega",
    "seguinte","irá","obrigada",
}

def latest(prefix: str) -> Path:
    matches = sorted(ART.glob(f"{prefix}_*"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not matches:
        raise FileNotFoundError(f"artifact not found for prefix={prefix}")
    return matches[0]



def is_valid_ru_translation(lemma: str, ru: str) -> bool:
    ru_l = ru.strip().lower()

    # reject empty or too short
    if not ru_l or len(ru_l) < 3:
        return False

    # reject latin leftovers
    if any(c.isascii() and c.isalpha() for c in ru_l):
        return False

    # reject stop garbage
    bad = {"для","почти","такой","это","тот","там","здесь"}
    if ru_l in bad:
        return False

    # reject transliteration (very rough)
    if ru_l.startswith(lemma[:3]):
        return False

    # reject verbs/adjectives heuristics
    if ru_l.endswith(("ый","ий","ой","ая","ое","ые","ать","ить","ться")):
        return False

    return True

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-report", default="", help="Path to top400_needs_manual_ru_v2.json")
    args = ap.parse_args()

    if args.source_report:
        src = Path(args.source_report)
    else:
        src = latest("noun_remediation_report_v2") / "top400_needs_manual_ru_v2.json"

    rows = json.loads(src.read_text(encoding="utf-8"))

    safe, rejected = [], []
    for row in rows:
        lemma = row["lemma"]
        reasons = []

        if lemma not in PREFER:
            reasons.append("not_in_prefer_list")
        if lemma in BLOCKED_LEMMAS:
            reasons.append("blocked_lemma")

        if reasons:
            rejected.append({
                "lemma": lemma,
                "freq_rank": row["freq_rank"],
                "ru_gloss": row["ru_gloss"],
                "reasons": reasons,
            })
        else:
            safe.append({
                "lemma": lemma,
                "freq_rank": row["freq_rank"],
                "ru_gloss": row["ru_gloss"],
                "source_file": row["source_file"],
            })

    outdir = ART / f"noun_bulk_prep_v4_{time.strftime('%Y%m%d_%H%M%S')}"
    outdir.mkdir(parents=True, exist_ok=True)

    stub = {row["lemma"]: "" for row in safe}

    (outdir / "safe_shortlist_v4.json").write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
    (outdir / "manual_ru_map_stub_v5.json").write_text(json.dumps(stub, ensure_ascii=False, indent=2), encoding="utf-8")
    (outdir / "rejected_v4.json").write_text(json.dumps(rejected, ensure_ascii=False, indent=2), encoding="utf-8")

    report = {
        "source_report": str(src),
        "safe_shortlist_total": len(safe),
        "rejected_total": len(rejected),
        "safe_shortlist_top50": safe[:50],
        "artifacts": {
            "safe_shortlist_v4": str(outdir / "safe_shortlist_v4.json"),
            "manual_ru_map_stub_v5": str(outdir / "manual_ru_map_stub_v5.json"),
            "rejected_v4": str(outdir / "rejected_v4.json"),
        }
    }
    (outdir / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(outdir / "summary.json")

if __name__ == "__main__":
    main()
