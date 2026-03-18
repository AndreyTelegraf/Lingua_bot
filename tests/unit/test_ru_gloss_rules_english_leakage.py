from services.vocab_qa.ru_gloss_rules import evaluate_ru_gloss


def test_best_best_reject():
    r = evaluate_ru_gloss(lemma="best", pos="noun", gloss="best")
    assert r.status == "reject"
    assert "english_leakage" in r.flags


def test_mixed_script_reject():
    r = evaluate_ru_gloss(lemma="algo", pos="noun", gloss="best друг")
    assert r.status == "reject"
    assert "mixed_script" in r.flags
