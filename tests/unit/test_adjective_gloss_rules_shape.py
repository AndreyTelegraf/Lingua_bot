from services.vocab_qa.adjective_gloss_rules import evaluate_adjective_ru_gloss

def test_good_adjective_ok():
    r = evaluate_adjective_ru_gloss(lemma="bonito", pos="adjective", gloss="красивый")
    assert r.status == "ok"

def test_noun_like_review():
    r = evaluate_adjective_ru_gloss(lemma="bonito", pos="adjective", gloss="кровать")
    assert r.status in {"review", "reject"}
    assert "non_adjective_gloss_candidate" in r.flags

def test_verb_like_review():
    r = evaluate_adjective_ru_gloss(lemma="bonito", pos="adjective", gloss="делать")
    assert r.status in {"review", "reject"}
    assert "verb_like_gloss" in r.flags
