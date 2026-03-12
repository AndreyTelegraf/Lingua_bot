#!/usr/bin/env bash
set -euo pipefail

DB_PATH="${1:-./data/lingua.db}"

sqlite3 "$DB_PATH" ".schema"
