#!/bin/bash
# apply_staging_microbatch.sh
# Wave: noun/10K/B2-C1 — batch 1 (49 items)
# Source: diagnostics_exports/current/import_ready.csv
# Generated: 2026-04-18
#
# BLOCKED items NOT in this script (require distractor fixes first):
#   G008 lençol   — простыня collides with active travesseiro distractors
#   G009 colchão  — матрас collides with active travesseiro distractors;
#                   подушка (active CA for travesseiro) used as distractor
#   G011 prateleira — ящик (active CA for caixa) used as distractor
#   G012 cabide    — ящик (active CA for caixa) used as distractor
#
# INTRA-CLUSTER WARN (managed by selector, not a blocking issue):
#   Birds (G064/G065/G066), reptiles (G068/G069), seafood (G076/G078/G079),
#   grains (G055/G056), mammals (G071/G072/G073), kinship (G030/G031),
#   body-parts pairs (G001/G003, G004/G006), building-parts (G016/G017),
#   forest-floor (G062/G063) — see import_ready.csv collision_note column.
#
# IMPORTANT: Items are inserted with is_active=0.
#   Do NOT activate items without ChatGPT review of approved.csv.
#   Activate selectively: do not activate all items from a cluster simultaneously
#   without verifying selector cluster caps are enforced.
#
# Usage:
#   ./apply_staging_microbatch.sh            # dry-run (default)
#   ./apply_staging_microbatch.sh --apply    # apply changes
#
# Run from project root: cd /Users/andreytelegraf/Projects/lingua_bot_v2

set -euo pipefail

DB="data/lingua_staging.db"
BACKUP_DIR="tmp/db_backups"
STAMP=$(date +%Y%m%dT%H%M%SZ)
DRY_RUN=1

if [[ "${1:-}" == "--apply" ]]; then
  DRY_RUN=0
fi

if [[ ! -f "$DB" ]]; then
  echo "ERROR: DB not found at $DB — run from project root" >&2
  exit 1
fi

echo "=== NOUN/10K WAVE 1 STAGING MICROBATCH ==="
echo "DB:      $DB"
echo "Items:   49 READY / 4 BLOCKED (not included)"
echo "Mode:    $([ $DRY_RUN -eq 1 ] && echo DRY-RUN || echo APPLY)"
echo ""

# Pre-flight: verify no ID conflicts
echo "--- Pre-flight checks ---"
EXISTING_IDS=$(sqlite3 "$DB" "SELECT COUNT(*) FROM vocab_items WHERE id BETWEEN 10729 AND 10777;")
if [[ "$EXISTING_IDS" -ne 0 ]]; then
  echo "ERROR: $EXISTING_IDS item IDs in range 10729-10777 already exist. Aborting." >&2
  exit 1
fi
echo "ID range 10729-10777: clear ($EXISTING_IDS conflicts)"

# Pre-flight: verify anti-collision still holds
COLLISION=$(sqlite3 "$DB" "
SELECT COUNT(*) FROM vocab_choices vc
JOIN vocab_items vi ON vi.id = vc.item_id
WHERE vi.is_active = 1 AND vc.is_correct = 0
  AND vc.choice_text IN (
    'локоть','лодыжка','затылок','бровь','подбородок','усы',
    'чердак','подвал','болото','обрыв','град','роса',
    'невестка','зять','рана','костыль','игла','сито',
    'чайник','блюдце','миска','капуста','рожь','ячмень',
    'ветка','мох','гриб','сова','ястреб','ворон',
    'черепаха','ящерица','выдра','ёж','барсук','белка',
    'кабан','угорь','краб','мидия','черновик','засада',
    'профсоюз','бюджет','свидетель','повар','плита',
    'расточительство','участок'
  );
")
if [[ "$COLLISION" -ne 0 ]]; then
  echo "ERROR: $COLLISION anti-collision violations — a new correct_answer is an active distractor. Aborting." >&2
  exit 1
fi
echo "Anti-collision check (Rule 1a): PASS ($COLLISION violations)"

COLLISION2=$(sqlite3 "$DB" "
SELECT COUNT(*) FROM vocab_items
WHERE is_active = 1
  AND correct_answer IN (
    'колено','лодыжка','локоть','ступня','подбородок','висок','лоб',
    'ресница','зрачок','веко','борода','брови','бакенбарды',
    'одеяло','полотенце',
    
    'крыша','подвал','подъезд','чердак','чулан',
    'поляна','склон','чаща','вершина','ущелье',
    'иней','гроза','ливень','туман',
    'зять','тёща','свекровь','невестка','тесть',
    'шрам','синяк','ожог','трость','носилки','шина',
    'нить','шило','булавка','воронка','ковш','ведро',
    'кастрюля','сковорода','кувшин','чашка','кружка','поднос',
    'морковь','лук','репа','пшеница','ячмень','овёс','рожь',
    'кора','корень','лист','папоротник','гриб','лишайник','трава',
    'ворон','ястреб','цапля','сова','коршун',
    'ящерица','улитка','жаба','черепаха','змея',
    'бобёр','белка','ёж','рысь','выдра','барсук','лиса','куница','олень',
    'краб','лосось','мидия','креветка','угорь',
    'рукопись','конспект','чистовик',
    'осада','облава','сражение',
    'совет','устав','съезд',
    'расход','счёт','инвестиция',
    'обвиняемый','прокурор','присяжный',
    'официант','пекарь','кассир',
    'балка','доска','кирпич',
    'потери','трата','убыток',
    'загон','луг','пашня'
  );
")
if [[ "$COLLISION2" -ne 0 ]]; then
  echo "ERROR: $COLLISION2 anti-collision violations — an active correct_answer is used as a new distractor. Aborting." >&2
  exit 1
fi
echo "Anti-collision check (Rule 1b): PASS ($COLLISION2 violations)"

DUP=$(sqlite3 "$DB" "
SELECT COUNT(*) FROM vocab_items
WHERE pos='noun' AND bin_name='10K' AND is_active=1
  AND lemma IN (
    'cotovelo','tornozelo','nuca','sobrancelha','queixo','bigode',
    'sótão','porão','brejo','penhasco','granizo','orvalho',
    'nora','genro','ferida','muleta','agulha','peneira',
    'chaleira','pires','tigela','repolho','centeio','cevada',
    'galho','musgo','cogumelo','coruja','gavião','corvo',
    'tartaruga','lagarto','lontra','ouriço','texugo','esquilo',
    'javali','enguia','caranguejo','mexilhão','rascunho',
    'emboscada','sindicato','orçamento','testemunha','cozinheiro',
    'laje','desperdício','talhão'
  );
")
if [[ "$DUP" -ne 0 ]]; then
  echo "ERROR: $DUP duplicate lemma(s) found in active noun/10K. Aborting." >&2
  exit 1
fi
echo "Duplicate lemma check: PASS ($DUP conflicts)"
echo ""

if [[ $DRY_RUN -eq 1 ]]; then
  echo "DRY-RUN complete. Pre-flight passed."
  echo "Re-run with --apply to insert 49 items + 196 choices."
  exit 0
fi

# Backup
mkdir -p "$BACKUP_DIR"
BACKUP_PATH="$BACKUP_DIR/lingua_staging_before_noun10k_wave1_${STAMP}.db"
cp "$DB" "$BACKUP_PATH"
echo "Backup created: $BACKUP_PATH"

# Apply
echo "--- Inserting 49 vocab_items ---"
sqlite3 "$DB" <<'SQL'
BEGIN;

INSERT INTO vocab_items (id, lemma, question_text, correct_answer, difficulty_band, pos, topic_tag, is_active, bin_name, cefr_estimate, concept_group, donor_eligible) VALUES
(10729, 'cotovelo', 'Что значит это слово?

cotovelo', 'локоть', 'B2', 'noun', 'build:noun_10k_wave1', 0, '10K', 'B2', 'body_parts', 0),
(10730, 'tornozelo', 'Что значит это слово?

tornozelo', 'лодыжка', 'B2', 'noun', 'build:noun_10k_wave1', 0, '10K', 'B2', 'body_parts', 0),
(10731, 'nuca', 'Что значит это слово?

nuca', 'затылок', 'B2', 'noun', 'build:noun_10k_wave1', 0, '10K', 'B2', 'body_parts', 0),
(10732, 'sobrancelha', 'Что значит это слово?

sobrancelha', 'бровь', 'B2', 'noun', 'build:noun_10k_wave1', 0, '10K', 'B2', 'body_parts', 0),
(10733, 'queixo', 'Что значит это слово?

queixo', 'подбородок', 'B2', 'noun', 'build:noun_10k_wave1', 0, '10K', 'B2', 'body_parts', 0),
(10734, 'bigode', 'Что значит это слово?

bigode', 'усы', 'B2', 'noun', 'build:noun_10k_wave1', 0, '10K', 'B2', 'body_parts', 0),
(10735, 'sótão', 'Что значит это слово?

sótão', 'чердак', 'B2', 'noun', 'build:noun_10k_wave1', 0, '10K', 'B2', 'building_parts', 0),
(10736, 'porão', 'Что значит это слово?

porão', 'подвал', 'B2', 'noun', 'build:noun_10k_wave1', 0, '10K', 'B2', 'building_parts', 0),
(10737, 'brejo', 'Что значит это слово?

brejo', 'болото', 'B2', 'noun', 'build:noun_10k_wave1', 0, '10K', 'B2', 'landscape_nature', 0),
(10738, 'penhasco', 'Что значит это слово?

penhasco', 'обрыв', 'C1', 'noun', 'build:noun_10k_wave1', 0, '10K', 'C1', 'landscape_nature', 0),
(10739, 'granizo', 'Что значит это слово?

granizo', 'град', 'B2', 'noun', 'build:noun_10k_wave1', 0, '10K', 'B2', 'weather_phenomena', 0),
(10740, 'orvalho', 'Что значит это слово?

orvalho', 'роса', 'B2', 'noun', 'build:noun_10k_wave1', 0, '10K', 'B2', 'weather_phenomena', 0),
(10741, 'nora', 'Что значит это слово?

nora', 'невестка', 'B2', 'noun', 'build:noun_10k_wave1', 0, '10K', 'B2', 'kinship_social', 0),
(10742, 'genro', 'Что значит это слово?

genro', 'зять', 'B2', 'noun', 'build:noun_10k_wave1', 0, '10K', 'B2', 'kinship_social', 0),
(10743, 'ferida', 'Что значит это слово?

ferida', 'рана', 'B2', 'noun', 'build:noun_10k_wave1', 0, '10K', 'B2', 'medical', 0),
(10744, 'muleta', 'Что значит это слово?

muleta', 'костыль', 'B2', 'noun', 'build:noun_10k_wave1', 0, '10K', 'B2', 'medical', 0),
(10745, 'agulha', 'Что значит это слово?

agulha', 'игла', 'B2', 'noun', 'build:noun_10k_wave1', 0, '10K', 'B2', 'tools_kitchen', 0),
(10746, 'peneira', 'Что значит это слово?

peneira', 'сито', 'B2', 'noun', 'build:noun_10k_wave1', 0, '10K', 'B2', 'tools_kitchen', 0),
(10747, 'chaleira', 'Что значит это слово?

chaleira', 'чайник', 'B2', 'noun', 'build:noun_10k_wave1', 0, '10K', 'B2', 'tools_kitchen', 0),
(10748, 'pires', 'Что значит это слово?

pires', 'блюдце', 'B2', 'noun', 'build:noun_10k_wave1', 0, '10K', 'B2', 'tools_kitchen', 0),
(10749, 'tigela', 'Что значит это слово?

tigela', 'миска', 'B2', 'noun', 'build:noun_10k_wave1', 0, '10K', 'B2', 'tools_kitchen', 0),
(10750, 'repolho', 'Что значит это слово?

repolho', 'капуста', 'B2', 'noun', 'build:noun_10k_wave1', 0, '10K', 'B2', 'food_vegetables_grains', 0),
(10751, 'centeio', 'Что значит это слово?

centeio', 'рожь', 'C1', 'noun', 'build:noun_10k_wave1', 0, '10K', 'C1', 'food_vegetables_grains', 0),
(10752, 'cevada', 'Что значит это слово?

cevada', 'ячмень', 'C1', 'noun', 'build:noun_10k_wave1', 0, '10K', 'C1', 'food_vegetables_grains', 0),
(10753, 'galho', 'Что значит это слово?

galho', 'ветка', 'B2', 'noun', 'build:noun_10k_wave1', 0, '10K', 'B2', 'plant_parts', 0),
(10754, 'musgo', 'Что значит это слово?

musgo', 'мох', 'B2', 'noun', 'build:noun_10k_wave1', 0, '10K', 'B2', 'plant_parts', 0),
(10755, 'cogumelo', 'Что значит это слово?

cogumelo', 'гриб', 'B2', 'noun', 'build:noun_10k_wave1', 0, '10K', 'B2', 'plant_parts', 0),
(10756, 'coruja', 'Что значит это слово?

coruja', 'сова', 'B2', 'noun', 'build:noun_10k_wave1', 0, '10K', 'B2', 'birds', 0),
(10757, 'gavião', 'Что значит это слово?

gavião', 'ястреб', 'B2', 'noun', 'build:noun_10k_wave1', 0, '10K', 'B2', 'birds', 0),
(10758, 'corvo', 'Что значит это слово?

corvo', 'ворон', 'B2', 'noun', 'build:noun_10k_wave1', 0, '10K', 'B2', 'birds', 0),
(10759, 'tartaruga', 'Что значит это слово?

tartaruga', 'черепаха', 'B2', 'noun', 'build:noun_10k_wave1', 0, '10K', 'B2', 'reptiles_amphibians', 0),
(10760, 'lagarto', 'Что значит это слово?

lagarto', 'ящерица', 'B2', 'noun', 'build:noun_10k_wave1', 0, '10K', 'B2', 'reptiles_amphibians', 0),
(10761, 'lontra', 'Что значит это слово?

lontra', 'выдра', 'C1', 'noun', 'build:noun_10k_wave1', 0, '10K', 'C1', 'mammals_wild', 0),
(10762, 'ouriço', 'Что значит это слово?

ouriço', 'ёж', 'B2', 'noun', 'build:noun_10k_wave1', 0, '10K', 'B2', 'mammals_wild', 0),
(10763, 'texugo', 'Что значит это слово?

texugo', 'барсук', 'C1', 'noun', 'build:noun_10k_wave1', 0, '10K', 'C1', 'mammals_wild', 0),
(10764, 'esquilo', 'Что значит это слово?

esquilo', 'белка', 'B2', 'noun', 'build:noun_10k_wave1', 0, '10K', 'B2', 'mammals_wild', 0),
(10765, 'javali', 'Что значит это слово?

javali', 'кабан', 'B2', 'noun', 'build:noun_10k_wave1', 0, '10K', 'B2', 'mammals_wild', 0),
(10766, 'enguia', 'Что значит это слово?

enguia', 'угорь', 'C1', 'noun', 'build:noun_10k_wave1', 0, '10K', 'C1', 'aquatic', 0),
(10767, 'caranguejo', 'Что значит это слово?

caranguejo', 'краб', 'B2', 'noun', 'build:noun_10k_wave1', 0, '10K', 'B2', 'aquatic', 0),
(10768, 'mexilhão', 'Что значит это слово?

mexilhão', 'мидия', 'B2', 'noun', 'build:noun_10k_wave1', 0, '10K', 'B2', 'aquatic', 0),
(10769, 'rascunho', 'Что значит это слово?

rascunho', 'черновик', 'B2', 'noun', 'build:noun_10k_wave1', 0, '10K', 'B2', 'abstract_social_institutional', 0),
(10770, 'emboscada', 'Что значит это слово?

emboscada', 'засада', 'B2', 'noun', 'build:noun_10k_wave1', 0, '10K', 'B2', 'abstract_social_institutional', 0),
(10771, 'sindicato', 'Что значит это слово?

sindicato', 'профсоюз', 'B2', 'noun', 'build:noun_10k_wave1', 0, '10K', 'B2', 'abstract_social_institutional', 0),
(10772, 'orçamento', 'Что значит это слово?

orçamento', 'бюджет', 'B2', 'noun', 'build:noun_10k_wave1', 0, '10K', 'B2', 'abstract_social_institutional', 0),
(10773, 'testemunha', 'Что значит это слово?

testemunha', 'свидетель', 'B2', 'noun', 'build:noun_10k_wave1', 0, '10K', 'B2', 'abstract_social_institutional', 0),
(10774, 'cozinheiro', 'Что значит это слово?

cozinheiro', 'повар', 'B2', 'noun', 'build:noun_10k_wave1', 0, '10K', 'B2', 'abstract_social_institutional', 0),
(10775, 'laje', 'Что значит это слово?

laje', 'плита', 'C1', 'noun', 'build:noun_10k_wave1', 0, '10K', 'C1', 'construction', 0),
(10776, 'desperdício', 'Что значит это слово?

desperdício', 'расточительство', 'C1', 'noun', 'build:noun_10k_wave1', 0, '10K', 'C1', 'abstract_social_institutional', 0),
(10777, 'talhão', 'Что значит это слово?

talhão', 'участок', 'C1', 'noun', 'build:noun_10k_wave1', 0, '10K', 'C1', 'land_use', 0);

INSERT INTO vocab_choices (item_id, choice_text, is_correct, position_index) VALUES
(10729,'локоть',1,0),(10729,'колено',0,1),(10729,'лодыжка',0,2),(10729,'запястье',0,3),
(10730,'лодыжка',1,0),(10730,'локоть',0,1),(10730,'колено',0,2),(10730,'ступня',0,3),
(10731,'затылок',1,0),(10731,'подбородок',0,1),(10731,'висок',0,2),(10731,'лоб',0,3),
(10732,'бровь',1,0),(10732,'ресница',0,1),(10732,'зрачок',0,2),(10732,'веко',0,3),
(10733,'подбородок',1,0),(10733,'затылок',0,1),(10733,'висок',0,2),(10733,'лоб',0,3),
(10734,'усы',1,0),(10734,'борода',0,1),(10734,'брови',0,2),(10734,'бакенбарды',0,3),
(10735,'чердак',1,0),(10735,'крыша',0,1),(10735,'подвал',0,2),(10735,'подъезд',0,3),
(10736,'подвал',1,0),(10736,'крыша',0,1),(10736,'чердак',0,2),(10736,'чулан',0,3),
(10737,'болото',1,0),(10737,'поляна',0,1),(10737,'склон',0,2),(10737,'чаща',0,3),
(10738,'обрыв',1,0),(10738,'склон',0,1),(10738,'вершина',0,2),(10738,'ущелье',0,3),
(10739,'град',1,0),(10739,'иней',0,1),(10739,'гроза',0,2),(10739,'ливень',0,3),
(10740,'роса',1,0),(10740,'иней',0,1),(10740,'туман',0,2),(10740,'ливень',0,3),
(10741,'невестка',1,0),(10741,'зять',0,1),(10741,'тёща',0,2),(10741,'свекровь',0,3),
(10742,'зять',1,0),(10742,'невестка',0,1),(10742,'тесть',0,2),(10742,'тёща',0,3),
(10743,'рана',1,0),(10743,'шрам',0,1),(10743,'синяк',0,2),(10743,'ожог',0,3),
(10744,'костыль',1,0),(10744,'трость',0,1),(10744,'носилки',0,2),(10744,'шина',0,3),
(10745,'игла',1,0),(10745,'нить',0,1),(10745,'шило',0,2),(10745,'булавка',0,3),
(10746,'сито',1,0),(10746,'воронка',0,1),(10746,'ковш',0,2),(10746,'ведро',0,3),
(10747,'чайник',1,0),(10747,'кастрюля',0,1),(10747,'сковорода',0,2),(10747,'кувшин',0,3),
(10748,'блюдце',1,0),(10748,'чашка',0,1),(10748,'кружка',0,2),(10748,'поднос',0,3),
(10749,'миска',1,0),(10749,'кастрюля',0,1),(10749,'сковорода',0,2),(10749,'кувшин',0,3),
(10750,'капуста',1,0),(10750,'морковь',0,1),(10750,'лук',0,2),(10750,'репа',0,3),
(10751,'рожь',1,0),(10751,'пшеница',0,1),(10751,'ячмень',0,2),(10751,'овёс',0,3),
(10752,'ячмень',1,0),(10752,'рожь',0,1),(10752,'пшеница',0,2),(10752,'овёс',0,3),
(10753,'ветка',1,0),(10753,'кора',0,1),(10753,'корень',0,2),(10753,'лист',0,3),
(10754,'мох',1,0),(10754,'папоротник',0,1),(10754,'гриб',0,2),(10754,'лишайник',0,3),
(10755,'гриб',1,0),(10755,'мох',0,1),(10755,'папоротник',0,2),(10755,'трава',0,3),
(10756,'сова',1,0),(10756,'ворон',0,1),(10756,'ястреб',0,2),(10756,'цапля',0,3),
(10757,'ястреб',1,0),(10757,'сова',0,1),(10757,'ворон',0,2),(10757,'коршун',0,3),
(10758,'ворон',1,0),(10758,'сова',0,1),(10758,'ястреб',0,2),(10758,'цапля',0,3),
(10759,'черепаха',1,0),(10759,'ящерица',0,1),(10759,'улитка',0,2),(10759,'жаба',0,3),
(10760,'ящерица',1,0),(10760,'черепаха',0,1),(10760,'жаба',0,2),(10760,'змея',0,3),
(10761,'выдра',1,0),(10761,'бобёр',0,1),(10761,'белка',0,2),(10761,'ёж',0,3),
(10762,'ёж',1,0),(10762,'рысь',0,1),(10762,'выдра',0,2),(10762,'барсук',0,3),
(10763,'барсук',1,0),(10763,'ёж',0,1),(10763,'выдра',0,2),(10763,'рысь',0,3),
(10764,'белка',1,0),(10764,'лиса',0,1),(10764,'бобёр',0,2),(10764,'куница',0,3),
(10765,'кабан',1,0),(10765,'лиса',0,1),(10765,'рысь',0,2),(10765,'олень',0,3),
(10766,'угорь',1,0),(10766,'краб',0,1),(10766,'лосось',0,2),(10766,'мидия',0,3),
(10767,'краб',1,0),(10767,'креветка',0,1),(10767,'угорь',0,2),(10767,'мидия',0,3),
(10768,'мидия',1,0),(10768,'краб',0,1),(10768,'креветка',0,2),(10768,'угорь',0,3),
(10769,'черновик',1,0),(10769,'рукопись',0,1),(10769,'конспект',0,2),(10769,'чистовик',0,3),
(10770,'засада',1,0),(10770,'осада',0,1),(10770,'облава',0,2),(10770,'сражение',0,3),
(10771,'профсоюз',1,0),(10771,'совет',0,1),(10771,'устав',0,2),(10771,'съезд',0,3),
(10772,'бюджет',1,0),(10772,'расход',0,1),(10772,'счёт',0,2),(10772,'инвестиция',0,3),
(10773,'свидетель',1,0),(10773,'обвиняемый',0,1),(10773,'прокурор',0,2),(10773,'присяжный',0,3),
(10774,'повар',1,0),(10774,'официант',0,1),(10774,'пекарь',0,2),(10774,'кассир',0,3),
(10775,'плита',1,0),(10775,'балка',0,1),(10775,'доска',0,2),(10775,'кирпич',0,3),
(10776,'расточительство',1,0),(10776,'потери',0,1),(10776,'трата',0,2),(10776,'убыток',0,3),
(10777,'участок',1,0),(10777,'загон',0,1),(10777,'луг',0,2),(10777,'пашня',0,3);

COMMIT;
SQL

echo "--- Insert complete ---"
echo ""
echo "Verifying..."
ITEM_COUNT=$(sqlite3 "$DB" "SELECT COUNT(*) FROM vocab_items WHERE topic_tag='build:noun_10k_wave1';")
CHOICE_COUNT=$(sqlite3 "$DB" "SELECT COUNT(*) FROM vocab_choices vc JOIN vocab_items vi ON vi.id=vc.item_id WHERE vi.topic_tag='build:noun_10k_wave1';")
ACTIVE_COUNT=$(sqlite3 "$DB" "SELECT COUNT(*) FROM vocab_items WHERE topic_tag='build:noun_10k_wave1' AND is_active=1;")
BAD_CHOICE=$(sqlite3 "$DB" "SELECT COUNT(*) FROM vocab_items vi WHERE vi.topic_tag='build:noun_10k_wave1' AND (SELECT COUNT(*) FROM vocab_choices WHERE item_id=vi.id) != 4;")
BAD_CORRECT=$(sqlite3 "$DB" "SELECT COUNT(*) FROM vocab_items vi WHERE vi.topic_tag='build:noun_10k_wave1' AND (SELECT COUNT(*) FROM vocab_choices WHERE item_id=vi.id AND is_correct=1) != 1;")

echo "Items inserted:        $ITEM_COUNT (expected: 49)"
echo "Choices inserted:      $CHOICE_COUNT (expected: 196)"
echo "Active items:          $ACTIVE_COUNT (expected: 0)"
echo "Items with bad choices: $BAD_CHOICE (expected: 0)"
echo "Items bad correct cnt: $BAD_CORRECT (expected: 0)"

if [[ "$ITEM_COUNT" -eq 49 && "$CHOICE_COUNT" -eq 196 && "$ACTIVE_COUNT" -eq 0 && "$BAD_CHOICE" -eq 0 && "$BAD_CORRECT" -eq 0 ]]; then
  echo ""
  echo "APPLY: PASS"
  echo ""
  echo "Next: run post_apply_checks.sh, then submit to ChatGPT before activating."
else
  echo ""
  echo "APPLY: FAIL — counts do not match expected. Investigate before proceeding."
  exit 1
fi
