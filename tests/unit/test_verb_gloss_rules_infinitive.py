from services.vocab_qa.verb_gloss_rules import evaluate_verb_ru_gloss

def test_good_infinitive_ok():
    r = evaluate_verb_ru_gloss(lemma="abrir", pos="verb", gloss="открывать")
    assert r.status == "ok"

def test_non_verb_noun_review():
    r = evaluate_verb_ru_gloss(lemma="colar", pos="verb", gloss="клей")
    assert r.status in {"review", "reject"}
    assert "non_verb_gloss_candidate" in r.flags

def test_known_good_short_form_est_ok():
    r = evaluate_verb_ru_gloss(lemma="comer", pos="verb", gloss="есть")
    assert r.status == "ok"
    assert "not_infinitive_like" not in r.flags

def test_known_good_short_form_klast_ok():
    r = evaluate_verb_ru_gloss(lemma="colocar", pos="verb", gloss="класть")
    assert r.status == "ok"
    assert "not_infinitive_like" not in r.flags

def test_predpochtest_ok():
    r = evaluate_verb_ru_gloss(lemma="preferir", pos="verb", gloss="предпочесть")
    assert r.status == "ok"
    assert "not_infinitive_like" not in r.flags

def test_modal_predicative_review():
    r = evaluate_verb_ru_gloss(lemma="dever", pos="verb", gloss="должен")
    assert r.status in {"review", "reject"}
    assert "modal_or_predicative_gloss" in r.flags

def test_accented_reflexive_ok():
    r = evaluate_verb_ru_gloss(lemma="treinar", pos="verb", gloss="тренирова́ться")
    assert r.status == "ok"
    assert "not_infinitive_like" not in r.flags
