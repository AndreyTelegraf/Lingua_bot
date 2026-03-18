from services.vocab_qa.adjective_gloss_rules import evaluate_adjective_ru_gloss

def test_translit_reject():
    r = evaluate_adjective_ru_gloss(lemma="bonito", pos="adjective", gloss="бонито")
    assert r.status == "reject"
    assert "translit_like_ru" in r.flags
