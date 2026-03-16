# UNIVERSAL BANK PIPELINE — ТЗ

## 1. Цель

Создать единый универсальный pipeline для очистки и conditioning банка LinguaBot.

Pipeline должен заменить текущий набор одноразовых скриптов вида:

- build_2k_*_review_pack*
- cleanup_2k_*_*
- fix_2k_*_*
- build_2k_*_priority_audit*

и работать для любого слоя:

- pos: noun / verb / adjective / adverb
- bin: 2K / 5K / 10K / 20K

Работа только со staging:

data/lingua_staging.db

Prod DB не трогается.

---

## 2. Главный принцип

Весь слой обрабатывается **одной командой**.

Пример:

python3 tools/run_bank_layer_pipeline.py --pos adjective --bin 5K --full

Pipeline должен выполнять стандартную последовательность:

1. build review pack
2. cleanup inactive zero-choice duplicates
3. build priority audit
4. apply safe semantic fixes
5. rebuild priority audit
6. run tests (если флаг включён)
7. restart staging (если флаг включён)

---

## 3. Новые компоненты

### Orchestrator

tools/run_bank_layer_pipeline.py

Это entrypoint.

Он принимает CLI параметры и управляет всем проходом.

---

### Общая библиотека pipeline

tools/lib_bank_pipeline.py

Там должна жить вся логика:

- подключение к БД
- выборка rows по pos/bin
- duplicate detection
- cleanup
- audit builder
- safe semantic fixes
- export CSV / JSON
- manifest generation

---

### Canonical translation registry

data/bank_canonical_translations.json

Формат:

{
  "culpa|noun": {
    "canonical_ru": "вина",
    "allowed_ru_variants": ["вина","виновность"],
    "forbidden_ru_variants": ["изъян"],
    "status": "approved"
  }
}

Используется для:

- semantic auto-fix
- запрета плохих переводов
- audit mismatches

---

## 4. Layer manifest

Каждый запуск pipeline должен генерировать JSON отчёт.

Путь:

tmp/bank_pipeline_reports/

Пример имени:

noun_2K_20260316.json

Минимальные поля:

- pos
- bin_name
- before_total_rows
- after_total_rows
- active_rows
- valid_6_1_rows
- duplicate_groups_before
- duplicate_groups_after
- deleted_zero_choice_inactive_duplicates
- semantic_updates
- audit_rows_before_fix
- audit_rows_after_fix
- final_status

final_status:

PASS / FAIL

---

## 5. CLI

Обязательные аргументы:

--pos
--bin

Флаги:

--build-review-pack
--cleanup-zero-choice-dups
--build-priority-audit
--apply-safe-fixes
--purge-fully-inactive-dups
--run-tests
--restart-staging
--dry-run
--full

--full = полный проход слоя.

---

## 6. Structural gate

Для active rows должны выполняться:

- ровно 6 choices
- ровно 1 correct
- нет duplicate answers
- нет correct внутри distractors

Нарушение → item попадает в audit.

---

## 7. Duplicate cleanup rules

Автоматически можно удалять только:

inactive rows с zero choices,
если рядом есть usable duplicate.

Active rows автоматически не удаляются.

---

## 8. Safe semantic fixes

Разрешены только если:

lemma|pos найден в canonical registry.

Pipeline может заменить перевод только если:

- текущий перевод forbidden
- canonical_ru известен

Пример:

culpa → вина

---

## 9. Что запрещено автоматизировать

Pipeline не должен автоматически:

- деактивировать active rows
- пересобирать distractor pool
- менять перевод без canonical rule
- merge разных лемм

Такие случаи идут в audit.

---

## 10. Цель

После внедрения pipeline:

- очистка нового слоя = одна команда
- structural мусор удаляется автоматически
- duplicate cleanup автоматический
- ручная работа остаётся только для semantic suspects
