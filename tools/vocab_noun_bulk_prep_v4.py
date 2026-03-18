from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

ROOT = Path("/home/andrey/Projects/lingua_bot_v2")
DB = ROOT / "data/lingua_staging.db"
ART = ROOT / "artifacts"

SOURCE_REPORT = ROOT / "artifacts/noun_remediation_report_v2_20260318_020353/top400_needs_manual_ru_v2.json"
MAP_V2 = ROOT / "data/manual/noun_manual_ru_map_v2.json"
MAP_V3 = ROOT / "data/manual/noun_manual_ru_map_v3.json"
MAP_V4 = ROOT / "data/manual/noun_manual_ru_map_v4.json"

PREFER = {
    "quarto", "vista", "movimento", "presente", "situação", "maioria", "acesso", "apoio",
    "coração", "lista", "espaço", "assunto", "posição", "interesse", "motivo", "tribunal",
    "comida", "oportunidade", "código", "altura", "escolha", "faculdade", "diferença",
    "estilo", "líder", "visita", "conhecimento", "natureza", "departamento", "cuidado",
    "fundo", "fonte", "banda", "corte", "marca", "visão", "viver", "total", "sentido",
    "controle", "presente", "via", "jovem", "bastante", "oficial", "fato"
}

BLOCKED_LEMMA = {
    "essa", "nosso", "nossos", "toda", "tal", "for", "deixa", "veja", "olha",
    "amo", "obrigado", "obrigada", "controle", "seguinte", "irá", "teu", "além",
    "fora", "quase", "tanto", "nova", "brasileira"
}

BLOCKED_GLOSS_SUBSTR = [
    "afterlife", "beyond", "catafalque", "female equivalent", "used substantively",
    "only used in", "mediterranean parrotfish", "stew", "ox fight", "meliponine",
    "free kick", "prelate", "bass", "englishman", "someone bound", "chief, head, head man, boss"
]

def load_json(path: Path) -> dict | list:
    return json.loads(path.read_text(encoding="utf-8"))

def normalize(s: str) -> str:
    return " ".join((s or "").strip().lower().split())

def existing_lemmas(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT lower(trim(lemma)) FROM vocab_items WHERE pos = 'noun'").fetchall()
    return {str(r[0]) for r in rows}

def main() -> None:
    src = load_json(SOURCE_REPORT)
    existing_maps = {}
    for p in (MAP_V2, MAP_V3, MAP_V4):
        if p.exists():
            existing_maps.update(load_json(p))

    conn = sqlite3.connect(DB)
    existing = existing_lemmas(conn)
    conn.close()

    safe, rejected = [], []

    for row in src:
        lemma = row["lemma"]
        gloss = row["ru_gloss"]
        nlemma = normalize(lemma)
        ngloss = normalize(gloss)

        reasons = []

        if nlemma in existing:
            reasons.append("already_present")
        if lemma in existing_maps:
            reasons.append("already_mapped_v2_v3_v4")
        if lemma in BLOCKED_LEMMA:
            reasons.append("blocked_lemma")
        if any(x in ngloss for x in BLOCKED_GLOSS_SUBSTR):
            reasons.append("blocked_gloss")
        if lemma not in PREFER:
            reasons.append("not_in_prefer_list")

        if reasons:
            rejected.append({
                "lemma": lemma,
                "freq_rank": row["freq_rank"],
                "ru_gloss": gloss,
                "reasons": reasons,
            })
        else:
            safe.append({
                "lemma": lemma,
                "freq_rank": row["freq_rank"],
                "ru_gloss": gloss,
                "source_file": row.get("source_file", ""),
            })

    safe.sort(key=lambda x: (x["freq_rank"], x["lemma"]))
    rejected.sort(key=lambda x: (x["freq_rank"], x["lemma"]))

    stub = {row["lemma"]: "" for row in safe}

    outdir = ART / f"noun_bulk_prep_v4_{time.strftime('%Y%m%d_%H%M%S')}"
    outdir.mkdir(parents=True, exist_ok=True)

    (outdir / "safe_shortlist_v4.json").write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
    (outdir / "manual_ru_map_stub_v5.json").write_text(json.dumps(stub, ensure_ascii=False, indent=2), encoding="utf-8")
    (outdir / "rejected_v4.json").write_text(json.dumps(rejected, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = {
        "source_report": str(SOURCE_REPORT),
        "safe_shortlist_total": len(safe),
        "rejected_total": len(rejected),
        "safe_shortlist_top50": safe[:50],
        "artifacts": {
            "safe_shortlist_v4": str(outdir / "safe_shortlist_v4.json"),
            "manual_ru_map_stub_v5": str(outdir / "manual_ru_map_stub_v5.json"),
            "rejected_v4": str(outdir / "rejected_v4.json"),
        },
    }
    (outdir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(outdir / "summary.json")

if __name__ == "__main__":
    main()
