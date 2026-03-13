#!/usr/bin/env bash
set -euo pipefail

DB_PATH="${1:-data/lingua_staging.db}"
OUT_DIR="${2:-scripts/qa_reports}"
STAMP="$(date +%Y%m%d_%H%M%S)"
REPORT="$OUT_DIR/vocab_bank_qa_${STAMP}.txt"
SNAPSHOT="$OUT_DIR/vocab_items_active_${STAMP}.sql"

mkdir -p "$OUT_DIR"

{
  echo "===== ACTIVE ITEMS ====="
  sqlite3 -header -column "$DB_PATH" "SELECT COUNT(*) AS active_items FROM vocab_items WHERE is_active=1;"

  echo
  echo "===== DUP LEMMA ====="
  sqlite3 -header -column "$DB_PATH" "
    SELECT lemma, COUNT(*) AS c
    FROM vocab_items
    WHERE is_active=1
    GROUP BY lemma
    HAVING c > 1
    LIMIT 50;
  "

  echo
  echo "===== DUP QUESTION_TEXT ====="
  sqlite3 -header -column "$DB_PATH" "
    SELECT question_text, COUNT(*) AS c
    FROM vocab_items
    WHERE is_active=1
    GROUP BY question_text
    HAVING c > 1
    LIMIT 50;
  "

  echo
  echo "===== GENERIC QUESTIONS ====="
  sqlite3 -header -column "$DB_PATH" "
    SELECT id, lemma, question_text
    FROM vocab_items
    WHERE is_active=1
      AND question_text LIKE 'Что значит%'
    LIMIT 50;
  "

  echo
  echo "===== EXPORT SNAPSHOT ====="
  sqlite3 "$DB_PATH" <<SQL
.mode insert vocab_items
.output $SNAPSHOT
SELECT * FROM vocab_items WHERE is_active=1;
.output stdout
SQL

  echo
  echo "Snapshot: $SNAPSHOT"
} | tee "$REPORT"
