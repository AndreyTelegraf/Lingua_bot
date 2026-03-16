from tools.build_vocab_bank import ItemRow, semantic_reject_reasons, pick_distractors

def test_semantic_reject_reasons_catch_mixed_script() -> None:
    item = ItemRow(1, "palavra", "словo", "noun", 1000, "A1", "2K", 1)
    stats = {"noun": {"median": 7, "p90": 12}}
    reasons = semantic_reject_reasons(item, stats)
    assert "gloss_contains_latin" in reasons or "gloss_mixed_script" in reasons

def test_pick_distractors_returns_five_same_pos() -> None:
    target = ItemRow(1, "abrir", "открывать", "verb", 1000, "A1", "2K", 1)
    pool = [
        target,
        ItemRow(2, "fechar", "закрывать", "verb", 1010, "A1", "2K", 1),
        ItemRow(3, "escrever", "писать", "verb", 1020, "A1", "2K", 1),
        ItemRow(4, "trabalhar", "работать", "verb", 1030, "A1", "2K", 1),
        ItemRow(5, "melhorar", "улучшать", "verb", 1040, "A1", "2K", 1),
        ItemRow(6, "escolher", "выбирать", "verb", 1050, "A1", "2K", 1),
        ItemRow(7, "janela", "окно", "noun", 1060, "A1", "2K", 1),
    ]
    out = pick_distractors(target, pool)
    assert len(out) == 5
    assert all(x.pos == "verb" for x in out)
