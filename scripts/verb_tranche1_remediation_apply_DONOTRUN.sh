#!/usr/bin/env bash
# verb_tranche1_remediation_apply_DONOTRUN.sh
#
# DO NOT RUN THIS SCRIPT DIRECTLY.
# Human review required before execution.
# Applies distractor and CA remediation for 9 verb tranche1 items.
# All changes derived from verb_tranche1_remediation_proposals.json (Stage 2).
#
# To apply: review all statements below, then run against staging ONLY:
#   bash scripts/verb_tranche1_remediation_apply_DONOTRUN.sh data/lingua_staging.db
#
# Prereq: sqlite3 CLI available.

set -euo pipefail

DB="${1:-data/lingua_staging.db}"

echo "=== VERB TRANCHE1 REMEDIATION APPLY ==="
echo "DB: $DB"
echo ""

sqlite3 "$DB" <<'SQL'
BEGIN TRANSACTION;

-- ============================================================
-- CORRECT ANSWER UPDATES (8 items; inventar CA kept)
-- ============================================================

-- acelerar (id=868): торопить → ускорять
UPDATE vocab_items SET correct_answer = 'ускорять' WHERE id = 868;

-- alterar (id=921): менять → изменять
UPDATE vocab_items SET correct_answer = 'изменять' WHERE id = 921;

-- implementar (id=1732): выполнять → реализовывать
UPDATE vocab_items SET correct_answer = 'реализовывать' WHERE id = 1732;

-- instalar (id=1759): провести → устанавливать
UPDATE vocab_items SET correct_answer = 'устанавливать' WHERE id = 1759;

-- pintar (id=2172): писать → красить
UPDATE vocab_items SET correct_answer = 'красить' WHERE id = 2172;

-- aproximar (id=3467): оценивать → приближать
UPDATE vocab_items SET correct_answer = 'приближать' WHERE id = 3467;

-- cancelar (id=3491): нарушать → отменять
UPDATE vocab_items SET correct_answer = 'отменять' WHERE id = 3491;

-- curtir (id=3509): дубить → выделывать
UPDATE vocab_items SET correct_answer = 'выделывать' WHERE id = 3509;

-- ============================================================
-- CORRECT CHOICE TEXT UPDATES (sync with CA)
-- ============================================================

UPDATE vocab_choices SET choice_text = 'ускорять'     WHERE item_id = 868  AND is_correct = 1;
UPDATE vocab_choices SET choice_text = 'изменять'     WHERE item_id = 921  AND is_correct = 1;
UPDATE vocab_choices SET choice_text = 'реализовывать' WHERE item_id = 1732 AND is_correct = 1;
UPDATE vocab_choices SET choice_text = 'устанавливать' WHERE item_id = 1759 AND is_correct = 1;
UPDATE vocab_choices SET choice_text = 'красить'       WHERE item_id = 2172 AND is_correct = 1;
UPDATE vocab_choices SET choice_text = 'приближать'    WHERE item_id = 3467 AND is_correct = 1;
UPDATE vocab_choices SET choice_text = 'отменять'      WHERE item_id = 3491 AND is_correct = 1;
UPDATE vocab_choices SET choice_text = 'выделывать'    WHERE item_id = 3509 AND is_correct = 1;

-- ============================================================
-- DISTRACTOR REPLACEMENTS
-- ============================================================

-- acelerar (id=868)
UPDATE vocab_choices SET choice_text = 'замедлять'       WHERE id = 403627;
UPDATE vocab_choices SET choice_text = 'тормозить'       WHERE id = 403628;
UPDATE vocab_choices SET choice_text = 'мчаться'         WHERE id = 403630;
UPDATE vocab_choices SET choice_text = 'разгонять'       WHERE id = 403631;
UPDATE vocab_choices SET choice_text = 'приостанавливать' WHERE id = 403632;

-- alterar (id=921)
UPDATE vocab_choices SET choice_text = 'уточнять'   WHERE id = 403124;
UPDATE vocab_choices SET choice_text = 'обновлять'  WHERE id = 403125;
UPDATE vocab_choices SET choice_text = 'откладывать' WHERE id = 403126;
-- 403127 (стрелять) — KEEP
UPDATE vocab_choices SET choice_text = 'удалять'    WHERE id = 403128;

-- implementar (id=1732)
UPDATE vocab_choices SET choice_text = 'планировать'   WHERE id = 403382;
UPDATE vocab_choices SET choice_text = 'разрабатывать' WHERE id = 403383;
-- 403384 (катиться) — KEEP
UPDATE vocab_choices SET choice_text = 'завершать'     WHERE id = 403385;
UPDATE vocab_choices SET choice_text = 'составлять'    WHERE id = 403386;

-- instalar (id=1759)
UPDATE vocab_choices SET choice_text = 'разбирать'   WHERE id = 403261;
UPDATE vocab_choices SET choice_text = 'перемещать'  WHERE id = 403263;
-- 403264 (нравиться) — KEEP
UPDATE vocab_choices SET choice_text = 'обрабатывать' WHERE id = 403265;
UPDATE vocab_choices SET choice_text = 'запускать'   WHERE id = 403266;

-- pintar (id=2172)
UPDATE vocab_choices SET choice_text = 'моделировать'  WHERE id = 403171;
-- 403172 (стрелять) — KEEP
UPDATE vocab_choices SET choice_text = 'конструировать' WHERE id = 403173;
-- 403174 (провести) — KEEP
UPDATE vocab_choices SET choice_text = 'формировать'   WHERE id = 403175;

-- aproximar (id=3467)
UPDATE vocab_choices SET choice_text = 'отдаляться' WHERE id = 403081;
UPDATE vocab_choices SET choice_text = 'разделять'  WHERE id = 403082;
-- 403083 (дубить) — KEEP
UPDATE vocab_choices SET choice_text = 'сталкивать' WHERE id = 403084;
UPDATE vocab_choices SET choice_text = 'окружать'   WHERE id = 403085;

-- cancelar (id=3491)
UPDATE vocab_choices SET choice_text = 'продлевать'   WHERE id = 403087;
UPDATE vocab_choices SET choice_text = 'одобрять'     WHERE id = 403088;
UPDATE vocab_choices SET choice_text = 'подтверждать' WHERE id = 403089;
UPDATE vocab_choices SET choice_text = 'перебивать'   WHERE id = 403091;
UPDATE vocab_choices SET choice_text = 'допускать'    WHERE id = 403092;

-- curtir (id=3509)
UPDATE vocab_choices SET choice_text = 'замачивать'  WHERE id = 433777;
UPDATE vocab_choices SET choice_text = 'очищать'     WHERE id = 433778;
UPDATE vocab_choices SET choice_text = 'смягчать'    WHERE id = 433779;
UPDATE vocab_choices SET choice_text = 'пропитывать' WHERE id = 433780;
UPDATE vocab_choices SET choice_text = 'отмачивать'  WHERE id = 433781;

-- inventar (id=9328) — CA kept
UPDATE vocab_choices SET choice_text = 'проектировать'  WHERE id = 404780;
UPDATE vocab_choices SET choice_text = 'формулировать'  WHERE id = 404781;
UPDATE vocab_choices SET choice_text = 'объединять'     WHERE id = 404782;
-- 404783 (бросить) — KEEP
UPDATE vocab_choices SET choice_text = 'преувеличивать' WHERE id = 404784;

COMMIT;
SQL

echo "Done. Verify with:"
echo "  python3 scripts/verb_tranche1_remediation_validate.py --db $DB"
