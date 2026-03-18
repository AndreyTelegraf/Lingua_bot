from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

ROOT = Path("/home/andrey/Projects/lingua_bot_v2")
DB = ROOT / "data/lingua_staging.db"
ART = ROOT / "artifacts"

REPORT_GLOB = "noun_remediation_report_v1_*"
MANUAL_MAP_V2 = ROOT / "data/manual/noun_manual_ru_map_v2.json"

BLOCKED_LEMMAS = {
    "essa","nosso","nossos","toda","for","veja","olha","deixa","entanto",
    "forte","tal","oficial","principal","viver","livre","interior",
}
BLOCKED_GLOSS_SUBSTR = [
    "surname", "municipality", "river", "greeting", "good morning",
    "good afternoon", "good evening", "female equivalent", "only used in",
    "ellips", "nickname", "letter", "script", "tribe", "misspelling",
    "pre-reform", "obsolete", "parrotfish", "stew", "cue",
]
PREFER_LEMMAS = {
    "ontem","seis","amanhã","carro","cima","fundo","fonte","banda","faculdade",
    "sorte","corte","marca","visão","milhões","quatro","maioria","acesso",
    "coração","lista","espaço","apoio","idade","sala","conselho","encontro",
    "assunto","igreja","posição","chefe","busca","interesse","motivo",
    "tribunal","comida","oportunidade","código","altura","escolha","prêmio",
    "diferença","estilo","líder","resto","visita","conhecimento","mente",
    "natureza","departamento","começo","chão","cuidado",
}

def norm(s: str) -> str:
    return " ".join((s or "").strip().lower().split())

def latest_report_dir() -> Path:
    cands = sorted((ROOT / "artifacts").glob(REPORT_GLOB), key=lambda p: p.name, reverse=True)
    if not cands:
        raise FileNotFoundError("noun remediation report artifact not found")
    return cands[-1] if False else max(cands, key=lambda p: p.stat().st_mtime)

def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))

def existing_nouns(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT lower(trim(lemma)) FROM vocab_items WHERE pos='noun'").fetchall()
    return {str(r[0]) for r in rows}

def blocked_gloss(gloss: str) -> bool:
    low = norm(gloss)
    return any(x in low for x in BLOCKED_GLOSS_SUBSTR)

def main() -> None:
    report_dir = latest_report_dir()
    src = report_dir / "top150_needs_manual_ru.json"
    rows = load_json(src)

    manual_map_v2 = load_json(MANUAL_MAP_V2) if MANUAL_MAP_V2.exists() else {}

    conn = sqlite3.connect(DB)
    present = existing_nouns(conn)
    conn.close()

    safe = []
    rejected = []

    for row in rows:
        lemma = row["lemma"]
        gloss = row.get("ru_gloss", "")
        low = norm(lemma)
        reasons = []

        if low in present:
            reasons.append("already_present")
        if low in {norm(k) for k in manual_map_v2.keys()}:
            reasons.append("already_mapped_v2")
        if lemma in BLOCKED_LEMMAS:
            reasons.append("blocked_lemma")
        if blocked_gloss(gloss):
            reasons.append("blocked_gloss")
        if lemma not in PREFER_LEMMAS:
            reasons.append("not_in_prefer_list")

        if reasons:
            rejected.append({
                "lemma": lemma,
                "freq_rank": row["freq_rank"],
                "ru_gloss": gloss,
                "reasons": reasons,
            })
            continue

        safe.append({
            "lemma": lemma,
            "freq_rank": row["freq_rank"],
            "ru_gloss": gloss,
            "source_file": row.get("source_file", ""),
        })

    safe.sort(key=lambda x: (x["freq_rank"], x["lemma"]))
    rejected.sort(key=lambda x: (x["freq_rank"], x["lemma"]))

    outdir = ART / f"noun_bulk_prep_v3_{time.strftime('%Y%m%d_%H%M%S')}"
    outdir.mkdir(parents=True, exist_ok=True)

    stub = {row["lemma"]: "" for row in safe}

    (outdir / "safe_shortlist_v3.json").write_text(
        json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (outdir / "manual_ru_map_stub_v3.json").write_text(
        json.dumps(stub, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (outdir / "rejected_v3.json").write_text(
        json.dumps(rejected, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    summary = {
        "source_report": str(src),
        "safe_shortlist_total": len(safe),
        "rejected_total": len(rejected),
        "safe_shortlist_top50": safe[:50],
        "artifacts": {
            "safe_shortlist_v3": str(outdir / "safe_shortlist_v3.json"),
            "manual_ru_map_stub_v3": str(outdir / "manual_ru_map_stub_v3.json"),
            "rejected_v3": str(outdir / "rejected_v3.json"),
        },
    }
    (outdir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(outdir / "summary.json")

if __name__ == "__main__":
    main()
