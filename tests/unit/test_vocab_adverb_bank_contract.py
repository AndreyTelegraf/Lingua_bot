from __future__ import annotations

import sqlite3


DB_PATH = 'data/lingua_staging.db'


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def test_active_adverb_bank_has_no_duplicate_lemmas() -> None:
    conn = _conn()
    try:
        rows = conn.execute(
            '''
            SELECT LOWER(TRIM(lemma)) AS lemma_key, COUNT(*) AS n
            FROM vocab_items
            WHERE is_active = 1
              AND pos = 'adverb'
              AND topic_tag LIKE 'build:pilot_ptpt_%'
            GROUP BY LOWER(TRIM(lemma))
            HAVING COUNT(*) > 1
            ORDER BY n DESC, lemma_key
            '''
        ).fetchall()
        assert rows == [], [
            {'lemma': str(r['lemma_key']), 'n': int(r['n'])}
            for r in rows
        ]
    finally:
        conn.close()


def test_active_adverb_bank_bin_contract() -> None:
    conn = _conn()
    try:
        rows = conn.execute(
            '''
            SELECT bin_name, COUNT(*) AS n
            FROM vocab_items
            WHERE is_active = 1
              AND pos = 'adverb'
              AND topic_tag LIKE 'build:pilot_ptpt_%'
            GROUP BY bin_name
            '''
        ).fetchall()
        got = {str(r['bin_name']): int(r['n']) for r in rows}

        assert got.get('1K', 0) >= 30, got
        assert got.get('2K', 0) >= 2, got
        assert got.get('5K', 0) >= 15, got
        assert got.get('10K', 0) >= 5, got
        assert got.get('20K', 0) >= 1, got
    finally:
        conn.close()


def test_active_adverb_bank_expected_mid_tail_set() -> None:
    conn = _conn()
    try:
        rows = conn.execute(
            '''
            SELECT lemma
            FROM vocab_items
            WHERE is_active = 1
              AND pos = 'adverb'
              AND topic_tag LIKE 'build:pilot_ptpt_%'
              AND LOWER(TRIM(lemma)) IN (
                  'frequentemente',
                  'raramente',
                  'geralmente',
                  'normalmente',
                  'especialmente',
                  'principalmente',
                  'claramente',
                  'obviamente',
                  'provavelmente',
                  'possivelmente',
                  'rapidamente',
                  'lentamente',
                  'facilmente',
                  'dificilmente',
                  'cuidadosamente',
                  'seriamente',
                  'simplesmente',
                  'realmente',
                  'totalmente',
                  'parcialmente'
              )
            ORDER BY lemma
            '''
        ).fetchall()

        got = {str(r['lemma']) for r in rows}
        expected = {
            'frequentemente',
            'raramente',
            'geralmente',
            'normalmente',
            'especialmente',
            'principalmente',
            'claramente',
            'obviamente',
            'provavelmente',
            'possivelmente',
            'rapidamente',
            'lentamente',
            'facilmente',
            'dificilmente',
            'cuidadosamente',
            'seriamente',
            'simplesmente',
            'realmente',
            'totalmente',
            'parcialmente',
        }
        assert got == expected, {'got': sorted(got), 'expected': sorted(expected)}
    finally:
        conn.close()
