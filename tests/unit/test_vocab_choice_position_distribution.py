import sqlite3


def test_demo_bank_correct_positions_are_not_constant() -> None:
    conn = sqlite3.connect("./data/lingua.db")
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT vi.lemma, vc.position_index
            FROM vocab_items vi
            JOIN vocab_choices vc ON vc.item_id = vi.id
            WHERE vc.is_correct = 1
              AND vi.lemma IN (
                'casa','comer','rápido','livro','água','trabalhar','abrir','feliz',
                'pequeno','ontem','janela','escrever','difícil','cedo',
                'estrada','escolher','estranho','talvez'
              )
            ORDER BY vi.lemma
            """
        ).fetchall()
        assert len(rows) == 18
        positions = [int(r["position_index"]) for r in rows]
        assert set(positions) == {1, 2, 3, 4, 5, 6}
        assert len(set(positions)) > 1
    finally:
        conn.close()
