from services.vocab_qa.ru_gloss_rules import evaluate_ru_gloss


def test_infinitive_for_noun_review_or_reject():
    r = evaluate_ru_gloss(lemma="prefeitura", pos="noun", gloss="делать")
    assert r.status in {"review", "reject"}
    assert "ru_gloss_verb_like" in r.flags
    assert "pos_mismatch_candidate" in r.flags


def test_adj_alone_is_weak_signal_now():
    r = evaluate_ru_gloss(lemma="humana", pos="noun", gloss="человеческий")
    assert r.status == "ok"
    assert "ru_gloss_adj_like" in r.flags
    assert "pos_mismatch_candidate" not in r.flags


def test_adj_plus_generic_is_review_or_reject():
    r = evaluate_ru_gloss(lemma="humana", pos="noun", gloss="женщина")
    assert r.status in {"review", "reject"}
    assert "generic_ai_gloss" in r.flags


def test_two_word_phrase_is_still_ok_for_now():
    r = evaluate_ru_gloss(lemma="boa", pos="noun", gloss="хорошая новость")
    assert r.status == "ok"
    assert "phrase_like_gloss" in r.flags


def test_three_word_phrase_is_review_or_reject():
    r = evaluate_ru_gloss(lemma="frente", pos="noun", gloss="очень важная часть")
    assert r.status in {"review", "reject"}
    assert "phrase_like_gloss" in r.flags


def test_smert_is_not_verb_like():
    r = evaluate_ru_gloss(lemma="morte", pos="noun", gloss="смерть")
    assert "ru_gloss_verb_like" not in r.flags


def test_pamyat_is_not_verb_like():
    r = evaluate_ru_gloss(lemma="memória", pos="noun", gloss="память")
    assert "ru_gloss_verb_like" not in r.flags


def test_krovat_is_not_verb_like():
    r = evaluate_ru_gloss(lemma="cama", pos="noun", gloss="кровать")
    assert "ru_gloss_verb_like" not in r.flags


def test_mat_is_not_verb_like():
    r = evaluate_ru_gloss(lemma="mãe", pos="noun", gloss="мать")
    assert "ru_gloss_verb_like" not in r.flags


def test_set_is_not_verb_like():
    r = evaluate_ru_gloss(lemma="rede", pos="noun", gloss="сеть")
    assert "ru_gloss_verb_like" not in r.flags


def test_mechet_is_not_verb_like():
    r = evaluate_ru_gloss(lemma="mesquita", pos="noun", gloss="мечеть")
    assert "ru_gloss_verb_like" not in r.flags


def test_put_is_not_verb_like():
    r = evaluate_ru_gloss(lemma="via", pos="noun", gloss="путь")
    assert "ru_gloss_verb_like" not in r.flags


def test_nogot_is_not_verb_like():
    r = evaluate_ru_gloss(lemma="unha", pos="noun", gloss="ноготь")
    assert "ru_gloss_verb_like" not in r.flags
