from __future__ import annotations

import csv
import json
import shutil
import sqlite3
from datetime import datetime, UTC
from pathlib import Path

BASE = Path("/home/andrey/Projects/lingua_bot_v2")
DB = BASE / "data" / "lingua_staging.db"

LATEST_PROBE = sorted(BASE.glob("artifacts/distractor_contract_v1_probe_*/distractor_contract_v1_rebuild.csv"))[-1]

TS = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
OUT_DIR = BASE / "artifacts" / f"distractor_contract_v1_apply_{TS}"
BACKUP = OUT_DIR / f"lingua_staging_before_distractor_contract_v1_apply_{TS}.db"

GENERIC_BAD = {
    "день", "мир", "жизнь", "час", "благо", "дело", "время", "путь",
    "текст", "город", "страна", "народ"
}

# Closed 1K noun cluster must not be reused as distractor ecosystem.
CLOSED_1K_NOUN_CLUSTER = {
    "день", "благо", "мир", "час", "жизнь", "город", "мать", "река", "ночь",
    "тип", "истина", "место", "семья", "народ", "страна"
}

BIN_ORDER = {"1K": 1, "2K": 2, "5K": 3, "10K": 4, "20K": 5}

def norm(s: str) -> str:
    return " ".join((s or "").strip().lower().split())

def fetch_item(conn: sqlite3.Connection, item_id: int) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT id, lemma, correct_answer, pos, bin_name, freq_rank, is_active
        FROM vocab_items
        WHERE id = ?
        """,
        (item_id,),
    ).fetchone()

def fetch_candidate_pool(
    conn: sqlite3.Connection,
    *,
    item_id: int,
    pos: str,
    bin_name: str | None,
    correct_answer: str,
) -> list[sqlite3.Row]:
    item_bin = str(bin_name or "").strip()
    item_bin_rank = BIN_ORDER.get(item_bin, 99)

    # Distractor Contract v1.1:
    # 1K nouns must not stay in a closed 1K-noun ecosystem.
    # For 1K nouns, prefer distractors from 2K/5K nouns.
    preferred_bins: set[str] | None = None
    allowed_bins: set[str] | None = None

    if pos == "noun" and item_bin == "1K":
        preferred_bins = {"2K", "5K"}
        allowed_bins = {"2K", "5K", "10K"}
    else:
        allowed_bins = {b for b, rank in BIN_ORDER.items() if abs(rank - item_bin_rank) <= 1}

    rows = conn.execute(
        """
        SELECT id, correct_answer, pos, bin_name, freq_rank
        FROM vocab_items
        WHERE is_active = 1
          AND id != ?
          AND pos = ?
        ORDER BY
          CASE WHEN freq_rank IS NULL THEN 1 ELSE 0 END,
          freq_rank ASC,
          id ASC
        """,
        (item_id, pos),
    ).fetchall()

    preferred: list[sqlite3.Row] = []
    fallback: list[sqlite3.Row] = []
    seen = {norm(correct_answer)}

    for r in rows:
        ans = str(r["correct_answer"] or "").strip()
        nans = norm(ans)
        row_bin = str(r["bin_name"] or "").strip()

        if not ans or nans in seen:
            continue
        if nans in GENERIC_BAD:
            continue
        if pos == "noun" and item_bin == "1K" and ans in CLOSED_1K_NOUN_CLUSTER:
            continue
        if allowed_bins is not None and row_bin not in allowed_bins:
            continue

        seen.add(nans)

        if preferred_bins is not None and row_bin in preferred_bins:
            preferred.append(r)
        else:
            fallback.append(r)

    return preferred + fallback

def replace_choices(conn: sqlite3.Connection, item_id: int, correct_answer: str, distractors: list[str]) -> None:
    conn.execute("DELETE FROM vocab_choices WHERE item_id = ?", (item_id,))
    choices = [correct_answer] + distractors[:5]
    for idx, txt in enumerate(choices):
        conn.execute(
            """
            INSERT INTO vocab_choices (item_id, choice_text, is_correct, position_index, created_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (item_id, txt, 1 if idx == 0 else 0, idx),
        )

def audit_item(conn: sqlite3.Connection, item_id: int) -> dict:
    rows = conn.execute(
        """
        SELECT choice_text, is_correct, position_index
        FROM vocab_choices
        WHERE item_id = ?
        ORDER BY position_index ASC, id ASC
        """,
        (item_id,),
    ).fetchall()
    choices = [str(r["choice_text"] or "") for r in rows]
    distractors = [x for x in choices if x]
    generic_hits = [x for x in distractors if norm(x) in GENERIC_BAD]
    return {
        "item_id": item_id,
        "choice_count": len(rows),
        "correct_count": sum(int(r["is_correct"] or 0) for r in rows),
        "unique_count": len(set(choices)),
        "generic_hits": generic_hits,
        "choices": choices,
    }

def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DB, BACKUP)

    with LATEST_PROBE.open(encoding="utf-8", newline="") as fh:
        rebuild_rows = list(csv.DictReader(fh))

    target_ids = sorted({int(r["id"]) for r in rebuild_rows if str(r.get("id", "")).isdigit()})

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    rebuilt = []
    skipped = []
    used_distractor_texts: dict[str, int] = {}
    used_pack_keys: set[str] = set()

    for item_id in target_ids:
        item = fetch_item(conn, item_id)
        if item is None:
            skipped.append({"id": item_id, "reason": "missing_item"})
            continue
        if int(item["is_active"] or 0) != 1:
            skipped.append({"id": item_id, "reason": "inactive_item"})
            continue

        pos = str(item["pos"] or "").strip()
        correct_answer = str(item["correct_answer"] or "").strip()
        bin_name = str(item["bin_name"] or "").strip() or None

        if not pos or not correct_answer:
            skipped.append({"id": item_id, "reason": "missing_pos_or_answer"})
            continue

        pool = fetch_candidate_pool(
            conn,
            item_id=item_id,
            pos=pos,
            bin_name=bin_name,
            correct_answer=correct_answer,
        )

        distractors = []
        local_seen = {norm(correct_answer)}
        for r in pool:
            ans = str(r["correct_answer"] or "").strip()
            nans = norm(ans)
            if not ans or nans in local_seen:
                continue
            if used_distractor_texts.get(nans, 0) >= 2:
                continue
            distractors.append(ans)
            local_seen.add(nans)
            if len(distractors) == 5:
                break

        if len(distractors) < 5:
            skipped.append({"id": item_id, "reason": f"not_enough_contract_candidates:{len(distractors)}"})
            continue

        pack_key = " | ".join(sorted(norm(x) for x in distractors))
        if pack_key in used_pack_keys:
            skipped.append({"id": item_id, "reason": "repeated_pack_blocked"})
            continue

        replace_choices(conn, item_id, correct_answer, distractors)
        used_pack_keys.add(pack_key)
        for x in distractors:
            nx = norm(x)
            used_distractor_texts[nx] = used_distractor_texts.get(nx, 0) + 1
        rebuilt.append({
            "id": item_id,
            "lemma": item["lemma"],
            "correct_answer": correct_answer,
            "pos": pos,
            "bin_name": item["bin_name"],
        })

    conn.commit()

    audits = [audit_item(conn, item_id) for item_id in target_ids if fetch_item(conn, item_id) is not None]

    summary = {
        "source_rebuild_csv": str(LATEST_PROBE),
        "output_dir": str(OUT_DIR),
        "db_backup": str(BACKUP),
        "target_ids": target_ids,
        "rebuilt_count": len(rebuilt),
        "skipped_count": len(skipped),
        "rebuilt": rebuilt,
        "skipped": skipped,
        "post_audit": audits,
    }

    (OUT_DIR / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    with (OUT_DIR / "rebuilt.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["id", "lemma", "correct_answer", "pos", "bin_name"])
        writer.writeheader()
        writer.writerows(rebuilt)

    with (OUT_DIR / "skipped.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["id", "reason"])
        writer.writeheader()
        writer.writerows(skipped)

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    conn.close()

if __name__ == "__main__":
    main()
