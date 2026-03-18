from services.vocab_qa.ru_gloss_rules import evaluate_ru_gloss


def test_long_phrase_reject():
    r = evaluate_ru_gloss(lemma="direta", pos="noun", gloss="ночь без сна и отдыха совсем")
    assert r.status == "reject"
    assert "too_long_for_noun_gloss" in r.flags


def test_short_reject():
    r = evaluate_ru_gloss(lemma="x", pos="noun", gloss=".")
    assert r.status == "reject"
    assert "too_short" in r.flags
