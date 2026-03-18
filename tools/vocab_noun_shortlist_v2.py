from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path("/home/andrey/Projects/lingua_bot_v2")
ART = ROOT / "artifacts"

BLOCK_LEMMAS = {
    "essa","toda","for","veja","olha","entanto","tal","teu","nosso","nossos",
    "brasileira","última","principal","oficial","seguinte","original","responsável",
    "interessante","suficiente","obrigado","obrigada","civil","popular","americano",
    "verde","humano","linda","preso","morto","perfeito","azul","direita",
    "próximo","próxima","pequeno","pequena","alta","baixo","chamada","chamado",
    "conhecido","sentido","material","profissional","controle","movimento",
    "livre","vista","presente","forte","total","via","acha","amo","irá","serão",
    "veio","leva","querer","andar","comer","olhar",
}

BLOCK_GLOSS_SUBSTR = [
    "only used in",
    "female equivalent of",
    "member of the",
    "mediterranean parrotfish",
    "dried fruit",
    "set of clothing traditionally worn together",
    "children (one's direct descendant",
    "youngster",
    "free kick",
    "englishman",
    "the present",
    "quarter; fourth",
    "crop (top of a plant)",
    "cue (action or event",
    "a stew prepared with",
    "rejection of a romantic proposal",
    "an unspecified or irrelevant amount",
    "a type of glossy wool fabric",
    "catafalque",
    "ours (used substantively",
    "one",
    "recent news",
]

PREFER_LEMMAS = {
    "maioria","acesso","coração","lista","espaço","apoio","ontem","situação",
    "amanhã","carro","viver","cima","fato","jovem","seis","quatro","milhões",
    "copa","idade","sala","conselho","encontro","assunto","igreja","posição",
    "chefe","busca","interesse","motivo","tribunal","ataque","fundo","comida",
    "oportunidade","código","fonte","altura","banda","escolha","faculdade",
    "prêmio","sorte","diferença","estilo","líder","resto","visita","zona",
    "conhecimento","interior","mente","celular","corte","marca","metade",
    "natureza","visão","departamento","começo","carreira","chão","cuidado",
}

def latest_report_dir() -> Path:
    candidates = sorted(ART.glob("noun_remediation_report_v1_*"), reverse=True)
    if not candidates:
        raise FileNotFoundError("noun_remediation_report_v1 artifact not found")
    return candidates[0]

def main() -> None:
    src_dir = latest_report_dir()
    src = src_dir / "top150_needs_manual_ru.json"
    rows = json.loads(src.read_text(encoding="utf-8"))

    safe = []
    rejected = []

    for row in rows:
        lemma = row["lemma"].strip()
        gloss = row["ru_gloss"].strip().lower()

        reasons = []
        if lemma in BLOCK_LEMMAS:
            reasons.append("blocked_lemma")
        if any(s in gloss for s in BLOCK_GLOSS_SUBSTR):
            reasons.append("blocked_gloss")
        if lemma not in PREFER_LEMMAS:
            reasons.append("not_in_prefer_list")

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
                "source_file": row.get("source_file", ""),
            })

    safe.sort(key=lambda x: (x["freq_rank"], x["lemma"]))
    rejected.sort(key=lambda x: (x["freq_rank"], x["lemma"]))

    manual_map_stub = {r["lemma"]: "" for r in safe}

    outdir = ART / f"noun_shortlist_v2_{time.strftime('%Y%m%d_%H%M%S')}"
    outdir.mkdir(parents=True, exist_ok=True)

    (outdir / "safe_shortlist.json").write_text(
        json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (outdir / "manual_ru_map_stub_v2.json").write_text(
        json.dumps(manual_map_stub, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (outdir / "rejected_from_top150.json").write_text(
        json.dumps(rejected, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    summary = {
        "source_report": str(src),
        "safe_shortlist_total": len(safe),
        "rejected_total": len(rejected),
        "safe_shortlist": safe,
        "artifacts": {
            "safe_shortlist": str(outdir / "safe_shortlist.json"),
            "manual_ru_map_stub_v2": str(outdir / "manual_ru_map_stub_v2.json"),
            "rejected_from_top150": str(outdir / "rejected_from_top150.json"),
        },
    }
    (outdir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(outdir / "summary.json")

if __name__ == "__main__":
    main()
