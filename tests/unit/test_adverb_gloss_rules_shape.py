from services.vocab_qa.adverb_gloss_rules import evaluate_adverb_ru_gloss

def test_good_adverb_ok():
    r = evaluate_adverb_ru_gloss(lemma="cedo", pos="adverb", gloss="рано")
    assert r.status == "ok"

def test_adjective_like_review():
    r = evaluate_adverb_ru_gloss(lemma="cedo", pos="adverb", gloss="хороший")
    assert r.status in {"review", "reject"}
    assert "non_adverb_gloss_candidate" in r.flags or "adjective_like_gloss" in r.flags

def test_verb_like_review():
    r = evaluate_adverb_ru_gloss(lemma="cedo", pos="adverb", gloss="делать")
    assert r.status in {"review", "reject"}
    assert "verb_like_gloss" in r.flags
