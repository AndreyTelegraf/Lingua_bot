#!/usr/bin/env bash
set -euo pipefail

DB_PATH="${1:-data/lingua_seed.db}"
SRC_DB="${2:-data/lingua_staging.db}"
SNAPSHOT_SQL="${3:-data/bank_snapshots/vocab_items_active_20260313.sql}"

rm -f "$DB_PATH"

echo "Creating DB from real vocab_items schema..."
sqlite3 "$SRC_DB" ".schema vocab_items" | sqlite3 "$DB_PATH"

echo "Loading active vocab snapshot..."
sqlite3 "$DB_PATH" < "$SNAPSHOT_SQL"

echo
echo "===== LOADED ITEMS ====="
sqlite3 -header -column "$DB_PATH" "SELECT COUNT(*) AS loaded_items FROM vocab_items;"

echo
echo "===== SCHEMA CHECK ====="
sqlite3 -header -column "$DB_PATH" "PRAGMA table_info(vocab_items);"
