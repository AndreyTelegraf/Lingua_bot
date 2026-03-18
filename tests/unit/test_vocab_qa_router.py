from services.vocab_qa.router import available_positions, get_audit_runner, reject_csv_name

def test_available_positions():
    assert available_positions() == ("noun", "verb", "adjective", "adverb")

def test_router_returns_callable():
    for pos in available_positions():
        fn = get_audit_runner(pos)
        assert callable(fn)

def test_reject_csv_name():
    assert reject_csv_name("noun") == "noun_ru_gloss_reject_auto.csv"
    assert reject_csv_name("verb") == "verb_ru_gloss_reject_auto.csv"
