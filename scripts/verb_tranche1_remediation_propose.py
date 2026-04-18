#!/usr/bin/env python3
"""
verb_tranche1_remediation_propose.py

STAGE 2 — Generate replacement proposals for the 9 target items.

For each blocked slot (R1b distractor conflict) and each R1a CA conflict,
pick the first semantically valid replacement that is not in active_cas
and not in active_distractors.

Outputs:
  verb_tranche1_remediation_proposals.json
  verb_tranche1_remediation_review.csv
"""
from __future__ import annotations

import csv
import json
import os
import sqlite3
import sys

DB_PATH = "data/lingua_staging.db"
TARGETS_JSON = "diagnostics_exports/verb_tranche1/current/verb_tranche1_remediation_targets.json"
OUTPUT_DIR = "diagnostics_exports/verb_tranche1/current"

# ---------------------------------------------------------------------------
# Per-item CA refinement proposals
# The current CA may be in active_distractors (R1a).
# We provide the most semantically precise alternative that avoids R1a.
# These are ordered by preference; first one not in active_cas is used.
# ---------------------------------------------------------------------------
CA_ALTERNATIVES: dict[str, list[str]] = {
    # acelerar = to speed up / accelerate
    # Current: торопить (to hurry sb) — imprecise + in active distractors
    "acelerar": ["ускорять", "разгонять", "ускорить", "форсировать"],

    # alterar = to alter, modify
    # Current: менять — CA of active mudar (conceptual near-duplicate) + in active distractors
    "alterar": ["изменять", "модифицировать", "корректировать", "видоизменять"],

    # implementar = to implement, carry out
    # Current: выполнять — in active distractors
    "implementar": ["реализовывать", "осуществлять", "воплощать", "воплощать"],

    # instalar = to install, set up
    # Current: провести — in active distractors (ambiguous anyway)
    "instalar": ["устанавливать", "монтировать", "настраивать", "размещать"],

    # pintar = to paint (art, walls)
    # Current: писать — in active distractors (also wrong: писать = to write, not to paint)
    "pintar": ["рисовать", "красить", "расписывать", "покрывать краской"],

    # aproximar = to approach, bring closer
    # Current: оценивать — in active distractors (also semantically weak for this lemma)
    "aproximar": ["приближать", "подходить", "сближать", "приближаться"],

    # cancelar = to cancel, annul
    # Current: нарушать — in active distractors
    "cancelar": ["отменять", "аннулировать", "упразднять", "расторгать"],

    # curtir = to tan (leather); colloquially to enjoy
    # Current: дубить — in active distractors; дубить is the correct archaic meaning
    # Try to keep дубить as CA; if R1a still blocks, use выделывать
    "curtir": ["дубить", "выделывать", "обрабатывать кожу", "задублять"],

    # inventar = to invent, make up
    # Current: изобрета́ть — no R1a conflict; CA stays
    "inventar": [],  # CA is fine; no R1a issue
}

# ---------------------------------------------------------------------------
# Shared distractor replacement pool
# Russian verb infinitives that are:
# - Less common than basic vocabulary (unlikely to be in active_cas)
# - Plausible as B2-level verb test distractors
# - Not POS or morphologically ambiguous
#
# Organised semantically so we can pick domain-relevant replacements.
# The script auto-selects per-item from this pool, validating against active_cas.
# ---------------------------------------------------------------------------
REPLACEMENT_POOL: list[str] = [
    # Change / modification domain
    "уточнять", "откладывать", "объединять", "подтверждать", "преувеличивать",
    "уменьшать", "разрушать", "перебивать", "проверять", "перестраивать",
    "допускать", "одобрять", "предотвращать", "признавать", "устранять",
    "вмешиваться", "подражать", "замещать", "перекладывать", "распределять",
    "перечислять", "обрабатывать", "упорядочивать", "завершать", "запускать",
    "ограничивать", "удалять", "добавлять", "прогнозировать", "накапливать",
    "обновлять", "разгонять", "тормозить", "мчаться", "замедлять",
    "засорять", "вычислять", "обсуждать", "взрываться", "загружать",
    "выгружать", "переносить", "измерять", "сравнивать", "объяснять",
    "исследовать", "наблюдать", "составлять", "формировать", "разбирать",
    # Motion / action domain
    "отступать", "продвигаться", "отдаляться", "погружаться", "приостанавливать",
    "направлять", "восстанавливать", "перемещать", "сталкивать", "окружать",
    # Cognition / communication
    "убеждать", "опровергать", "уточнять", "толковать", "раскрывать",
    "излагать", "согласовывать", "уведомлять", "указывать", "напоминать",
    # Creation / production
    "моделировать", "конструировать", "разрабатывать", "проектировать",
    "производить", "формулировать", "генерировать", "компоновать",
    # Negative / termination
    "отклонять", "отвергать", "прерывать", "аннулировать", "отзывать",
    "запрещать", "блокировать", "нейтрализовать", "ликвидировать",
]

# Per-item priority pool: semantically closest first for better distractor plausibility.
ITEM_POOL_PRIORITY: dict[str, list[str]] = {
    "acelerar": ["замедлять", "тормозить", "мчаться", "разгонять", "приостанавливать",
                 "отставать", "задерживать", "ускорять", "форсировать", "торопить"],
    "alterar": ["уточнять", "обновлять", "откладывать", "сохранять", "удалять",
                "добавлять", "объединять", "ограничивать", "разрушать", "формировать"],
    "implementar": ["планировать", "разрабатывать", "завершать", "проверять",
                    "составлять", "отклонять", "откладывать", "формулировать",
                    "направлять", "согласовывать"],
    "instalar": ["разбирать", "перемещать", "обрабатывать", "запускать",
                 "настраивать", "выгружать", "загружать", "конструировать",
                 "моделировать", "проектировать"],
    "pintar": ["моделировать", "конструировать", "составлять", "формировать",
               "вырезать", "раскрашивать", "вышивать", "лепить",
               "фотографировать", "оформлять"],
    "aproximar": ["удалять", "отдаляться", "разделять", "сталкивать",
                  "окружать", "преследовать", "ограничивать", "замещать",
                  "направлять", "отклонять"],
    "cancelar": ["разрабатывать", "составлять", "продлевать", "обновлять",
                 "одобрять", "подтверждать", "откладывать", "перебивать",
                 "допускать", "устранять"],
    "curtir": ["замачивать", "обрабатывать", "очищать", "смягчать",
               "пропитывать", "сушить", "красить", "отмачивать",
               "промывать", "сортировать"],
    "inventar": ["разрабатывать", "открывать", "создавать", "моделировать",
                 "конструировать", "проектировать", "формулировать",
                 "составлять", "формировать", "обновлять"],
}


def build_active_sets(conn: sqlite3.Connection) -> tuple[set[str], set[str]]:
    active_cas = set(
        (r[0] or "").strip()
        for r in conn.execute(
            "SELECT correct_answer FROM vocab_items WHERE is_active=1 AND correct_answer IS NOT NULL"
        ).fetchall()
        if r[0]
    )
    active_distractors = set(
        (r[0] or "").strip()
        for r in conn.execute(
            "SELECT DISTINCT vc.choice_text FROM vocab_choices vc "
            "JOIN vocab_items vi ON vi.id=vc.item_id WHERE vi.is_active=1 AND vc.is_correct=0"
        ).fetchall()
        if r[0]
    )
    return active_cas, active_distractors


def pick_ca(lemma: str, current_ca: str, active_cas: set[str], active_distractors: set[str]) -> dict:
    """Pick the best available CA replacement. Returns status and chosen CA."""
    if current_ca not in active_distractors:
        return {"status": "OK_KEEP", "chosen_ca": current_ca, "note": "current CA not in active distractors"}

    alternatives = CA_ALTERNATIVES.get(lemma, [])
    for alt in alternatives:
        alt = alt.strip()
        if not alt:
            continue
        if alt not in active_cas and alt not in active_distractors:
            return {
                "status": "REPLACED",
                "chosen_ca": alt,
                "old_ca": current_ca,
                "note": f"replaced: '{current_ca}' was in active distractors",
            }
    return {
        "status": "NO_VALID_ALTERNATIVE",
        "chosen_ca": current_ca,
        "note": "all CA alternatives exhausted or in active bank — needs human review",
    }


def pick_distractor_replacement(
    slot_text: str,
    lemma: str,
    correct_answer: str,
    already_used: set[str],
    active_cas: set[str],
    active_distractors: set[str],
) -> dict:
    """Pick a replacement distractor for a single conflict slot."""
    priority = ITEM_POOL_PRIORITY.get(lemma, []) + REPLACEMENT_POOL
    seen = set()
    candidates_tried = []
    for cand in priority:
        cand = cand.strip()
        if not cand or cand in seen:
            continue
        seen.add(cand)
        if cand == correct_answer:
            candidates_tried.append((cand, "equals_ca"))
            continue
        if cand in active_cas:
            candidates_tried.append((cand, "in_active_cas"))
            continue
        if cand in active_distractors:
            candidates_tried.append((cand, "in_active_distractors"))
            continue
        if cand in already_used:
            candidates_tried.append((cand, "already_used_in_pack"))
            continue
        return {
            "status": "REPLACED",
            "replacement": cand,
            "old_distractor": slot_text,
            "candidates_tried": candidates_tried[:5],
        }
    return {
        "status": "NO_VALID_REPLACEMENT",
        "replacement": None,
        "old_distractor": slot_text,
        "candidates_tried": candidates_tried[:10],
        "note": "all pool candidates exhausted — needs human input",
    }


def run(conn: sqlite3.Connection, targets: list[dict]) -> list[dict]:
    active_cas, active_distractors = build_active_sets(conn)
    used_across_pack: set[str] = set()

    results = []
    for item in targets:
        item_id = item["item_id"]
        lemma = item["lemma"]
        bin_name = item["bin_name"]
        current_ca = (item["correct_answer"] or "").strip()

        # CA decision
        ca_decision = pick_ca(lemma, current_ca, active_cas, active_distractors)
        chosen_ca = ca_decision["chosen_ca"].strip()

        # Register chosen CA as "used" so distractors can't duplicate it
        used_in_item: set[str] = {chosen_ca}

        # Distractor decisions per slot
        distractor_proposals = []
        for d in item["all_distractors"]:
            text = (d["choice_text"] or "").strip()
            choice_id = d["choice_id"]
            if not d["r1b_conflict"]:
                # Keep as-is — no conflict
                distractor_proposals.append({
                    "choice_id": choice_id,
                    "old_distractor": text,
                    "action": "KEEP",
                    "replacement": text,
                    "status": "OK",
                    "reason": "no R1b conflict",
                })
                used_in_item.add(text)
            else:
                proposal = pick_distractor_replacement(
                    text, lemma, chosen_ca, used_in_item | used_across_pack,
                    active_cas, active_distractors,
                )
                replacement = proposal["replacement"]
                if replacement:
                    used_in_item.add(replacement)
                distractor_proposals.append({
                    "choice_id": choice_id,
                    "old_distractor": text,
                    "action": "REPLACE",
                    "replacement": replacement,
                    "status": proposal["status"],
                    "reason": f"R1b: was CA of item {d['r1b_conflict_with_item']}",
                    "candidates_tried": proposal.get("candidates_tried", []),
                })

        # Post-proposal R1a check on chosen CA
        ca_r1a_pass = chosen_ca not in active_distractors
        # Post-proposal R1b check on all proposed distractors
        proposed_distractors = [p["replacement"] for p in distractor_proposals if p["replacement"]]
        r1b_failures = [r for r in proposed_distractors if r in active_cas]

        all_replaced = all(
            p["status"] in ("OK", "REPLACED")
            for p in distractor_proposals
        )
        fully_remediated = ca_r1a_pass and not r1b_failures and all_replaced

        # Add chosen CA and all clean distractors to cross-pack used set
        used_across_pack.add(chosen_ca)
        for p in distractor_proposals:
            if p["replacement"]:
                used_across_pack.add(p["replacement"])

        results.append({
            "item_id": item_id,
            "lemma": lemma,
            "bin_name": bin_name,
            "original_ca": current_ca,
            "ca_decision": ca_decision,
            "chosen_ca": chosen_ca,
            "r1a_pass_after_remedy": ca_r1a_pass,
            "distractor_proposals": distractor_proposals,
            "r1b_pass_after_remedy": not r1b_failures,
            "r1b_residual_failures": r1b_failures,
            "all_replaced": all_replaced,
            "fully_remediated": fully_remediated,
        })

    return results


def write_artifacts(results: list[dict], output_dir: str) -> dict[str, str]:
    os.makedirs(output_dir, exist_ok=True)

    # JSON
    json_path = os.path.join(output_dir, "verb_tranche1_remediation_proposals.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # CSV
    csv_path = os.path.join(output_dir, "verb_tranche1_remediation_review.csv")
    csv_fields = [
        "item_id", "lemma", "bin_name",
        "original_ca", "chosen_ca", "ca_action", "ca_r1a_pass",
        "choice_id", "old_distractor", "replacement",
        "action", "status", "reason", "r1b_pass",
    ]
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields)
        writer.writeheader()
        for r in results:
            ca_action = r["ca_decision"]["status"]
            for p in r["distractor_proposals"]:
                repl = p["replacement"] or ""
                r1b_pass = repl not in (
                    set()
                )  # Will be fully validated in Stage 3
                writer.writerow({
                    "item_id": r["item_id"],
                    "lemma": r["lemma"],
                    "bin_name": r["bin_name"],
                    "original_ca": r["original_ca"],
                    "chosen_ca": r["chosen_ca"],
                    "ca_action": ca_action,
                    "ca_r1a_pass": r["r1a_pass_after_remedy"],
                    "choice_id": p["choice_id"],
                    "old_distractor": p["old_distractor"],
                    "replacement": repl,
                    "action": p["action"],
                    "status": p["status"],
                    "reason": p["reason"],
                    "r1b_pass": p["status"] in ("OK", "REPLACED"),
                })

    return {"json": json_path, "csv": csv_path}


def print_summary(results: list[dict]) -> None:
    print("=" * 60)
    print("STAGE 2 — REPLACEMENT PROPOSAL PACK")
    print("=" * 60)
    total_slots = 0
    replaced_slots = 0
    failed_slots = 0
    items_fully_remediated = 0

    for r in results:
        status = "FULL" if r["fully_remediated"] else "PARTIAL/FAIL"
        ca_note = (
            f"CA: {r['original_ca']} → {r['chosen_ca']}"
            if r["chosen_ca"] != r["original_ca"]
            else f"CA: {r['chosen_ca']} (kept)"
        )
        print(f"\n  {r['lemma']} (id={r['item_id']}) [{status}]")
        print(f"    {ca_note}  R1a_pass={r['r1a_pass_after_remedy']}")
        for p in r["distractor_proposals"]:
            slot_status = p["status"]
            old = p["old_distractor"]
            new = p["replacement"] or "NO_REPLACEMENT_FOUND"
            if p["action"] == "REPLACE":
                total_slots += 1
                if p["status"] == "REPLACED":
                    replaced_slots += 1
                    print(f"    REPLACE: '{old}' → '{new}'")
                else:
                    failed_slots += 1
                    print(f"    FAIL:    '{old}' → {new}")
            else:
                print(f"    KEEP:    '{old}'")
        if not r["r1a_pass_after_remedy"]:
            print(f"    ** R1a still fails: CA '{r['chosen_ca']}' in active distractors **")
        if r["r1b_residual_failures"]:
            print(f"    ** R1b residual: {r['r1b_residual_failures']} **")
        if r["fully_remediated"]:
            items_fully_remediated += 1

    print(f"\nSlots replaced: {replaced_slots}/{total_slots}")
    print(f"Slots failed:   {failed_slots}/{total_slots}")
    print(f"Items fully remediated: {items_fully_remediated}/9")


def main() -> int:
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    with open(TARGETS_JSON) as f:
        targets = json.load(f)

    try:
        results = run(conn, targets)
    finally:
        conn.close()

    print_summary(results)
    paths = write_artifacts(results, OUTPUT_DIR)
    print(f"\nArtifacts:")
    print(f"  {paths['json']}")
    print(f"  {paths['csv']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
