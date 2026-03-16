from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path
from datetime import datetime, UTC

BASE = Path("/home/andrey/Projects/lingua_bot_v2")
DB = BASE / "data" / "lingua_staging.db"
OUT_DIR = BASE / "artifacts" / f"post_promotion_audit_v1_probe_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"

ARTIFACTS = {
    "expansion_gate_v1_2": sorted(BASE.glob("artifacts/expansion_gate_v1_2_apply_*/summary.json"))[-1],
    "safe_batch50_v1_3": sorted(BASE.glob("artifacts/safe_batch50_apply_*/summary.json"))[-1],
}

REVIEW6_IDS = [246, 255, 256, 257, 275, 299]

TRANSPARENT_HINTS = {
    "revista", "opinião", "médico", "negócio", "liberdade", "direção", "entrada",
    "seleção", "conjunto", "dado", "sinal", "aniversário", "massa", "pedido", "verão"
}

ABSTRACT_HINTS = {
    "liberdade", "opinião", "negócio", "conjunto", "dado", "sinal"
}

def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))

def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    keep_ids = set()
    meta_source = {}

    s1 = load_json(ARTIFACTS["expansion_gate_v1_2"])
    for item_id in s1.get("keep_ids", []):
        keep_ids.add(int(item_id))
        meta_source[int(item_id)] = "expansion_gate_v1_2"

    for item_id in REVIEW6_IDS:
        keep_ids.add(int(item_id))
        meta_source[int(item_id)] = "review6_keep"

    s2 = load_json(ARTIFACTS["safe_batch50_v1_3"])
    for item_id in s2.get("keep_ids", []):
        keep_ids.add(int(item_id))
        meta_source[int(item_id)] = "safe_batch50_v1_3"

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    rows = []
    for item_id in sorted(keep_ids):
        item = conn.execute("""
            SELECT id, lemma, question_text, correct_answer, pos, bin_name, level, freq_rank, is_active
            FROM vocab_items
            WHERE id = ?
        """, (item_id,)).fetchone()
        if not item:
            continue
        if int(item["is_active"] or 0) != 1:
            continue

        choices = [r["choice_text"] for r in conn.execute("""
            SELECT choice_text
            FROM vocab_choices
            WHERE item_id = ?
            ORDER BY position_index, id
        """, (item_id,)).fetchall()]

        lemma = item["lemma"] or ""
        flags = []
        notes = []

        if lemma in TRANSPARENT_HINTS:
            flags.append("TRANSPARENT_HINT")
        if lemma in ABSTRACT_HINTS:
            flags.append("ABSTRACT_HINT")
        if item["pos"] == "noun" and item["bin_name"] in {"1K", "2K"} and len(lemma) >= 10:
            flags.append("LONG_HIGH_FREQ_NOUN")
        if item["correct_answer"] and len(str(item["correct_answer"])) <= 3:
            flags.append("SHORT_TRANSLATION")

        rows.append({
            "source_layer": meta_source.get(item_id, ""),
            "id": item["id"],
            "lemma": item["lemma"],
            "question_text": item["question_text"],
            "correct_answer": item["correct_answer"],
            "pos": item["pos"],
            "bin_name": item["bin_name"],
            "level": item["level"] or "",
            "freq_rank": item["freq_rank"],
            "is_active": item["is_active"],
            "choice_count": len(choices),
            "choice_1": choices[0] if len(choices) > 0 else "",
            "choice_2": choices[1] if len(choices) > 1 else "",
            "choice_3": choices[2] if len(choices) > 2 else "",
            "choice_4": choices[3] if len(choices) > 3 else "",
            "choice_5": choices[4] if len(choices) > 4 else "",
            "choice_6": choices[5] if len(choices) > 5 else "",
            "audit_flags": ";".join(flags),
            "audit_notes": " | ".join(notes),
            "manual_audit_status": "",
            "manual_audit_reason": "",
            "manual_audit_notes": "",
        })

    out_csv = OUT_DIR / "post_promotion_audit_v1.csv"
    with out_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else [])
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "total_recently_promoted": len(rows),
        "by_source": {
            "expansion_gate_v1_2": sum(1 for r in rows if r["source_layer"] == "expansion_gate_v1_2"),
            "review6_keep": sum(1 for r in rows if r["source_layer"] == "review6_keep"),
            "safe_batch50_v1_3": sum(1 for r in rows if r["source_layer"] == "safe_batch50_v1_3"),
        },
        "flag_counts": {},
        "output_dir": str(OUT_DIR),
    }

    for r in rows:
        for f in (r["audit_flags"] or "").split(";"):
            if not f:
                continue
            summary["flag_counts"][f] = summary["flag_counts"].get(f, 0) + 1

    (OUT_DIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("\n===== TOP 80 PROMOTED FOR AUDIT =====")
    for i, r in enumerate(rows[:80], 1):
        print(f"{i:02d}. id={r['id']} lemma={r['lemma']} src={r['source_layer']} pos={r['pos']} bin={r['bin_name']} freq={r['freq_rank']} | {r['audit_flags']}")

    conn.close()

if __name__ == "__main__":
    main()
