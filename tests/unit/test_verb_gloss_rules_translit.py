from services.vocab_qa.verb_gloss_rules import evaluate_verb_ru_gloss

def test_translit_reject():
    r = evaluate_verb_ru_gloss(lemma="achar", pos="verb", gloss="ачар")
    assert r.status == "reject"
    assert "translit_like_ru" in r.flags
