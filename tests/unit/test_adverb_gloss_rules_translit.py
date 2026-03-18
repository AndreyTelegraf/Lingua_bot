from services.vocab_qa.adverb_gloss_rules import evaluate_adverb_ru_gloss

def test_translit_reject():
    r = evaluate_adverb_ru_gloss(lemma="cedo", pos="adverb", gloss="седо")
    assert r.status == "reject"
    assert "translit_like_ru" in r.flags
