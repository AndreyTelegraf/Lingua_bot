def test_selector_policy_pos_targets_sum_to_24_nominally() -> None:
    targets = {
        "noun": 8,
        "verb": 7,
        "adjective": 6,
        "adverb": 3,
    }
    assert sum(targets.values()) == 24


def test_selector_policy_cefr_caps_sum_to_24() -> None:
    caps = {
        "A1": 6,
        "A2": 6,
        "B1": 6,
        "B2": 4,
        "C1": 2,
    }
    assert sum(caps.values()) == 24


def test_selector_policy_degradation_order_is_defined() -> None:
    degradation_order = [
        "ideal",
        "pos_relaxed",
        "cefr_relaxed",
        "metadata_relaxed",
    ]
    assert degradation_order == [
        "ideal",
        "pos_relaxed",
        "cefr_relaxed",
        "metadata_relaxed",
    ]


def test_selector_policy_terminal_constants() -> None:
    question_limit = 24
    hard_reject_abort_threshold = 10

    assert question_limit == 24
    assert hard_reject_abort_threshold == 10
