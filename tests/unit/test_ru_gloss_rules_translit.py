from services.vocab_qa.ru_gloss_rules import evaluate_ru_gloss


def test_durante_dyurant_reject():
    r = evaluate_ru_gloss(lemma="durante", pos="noun", gloss="дюрант")
    assert r.status == "reject"
    assert "translit_like_ru" in r.flags


def test_achar_achar_reject():
    r = evaluate_ru_gloss(lemma="achar", pos="noun", gloss="ачар")
    assert r.status == "reject"
    assert "lemma_phonetic_copy" in r.flags
