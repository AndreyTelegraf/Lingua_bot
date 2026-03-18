from __future__ import annotations

import re

PATTERNS = [
    r"^Как бы вы\b",
    r"^Чем в живой\b",
    r"^Как в живой\b",
    r"^Как по-португальски\b",
]


def test_patterns_match_expected_bad_openers() -> None:
    compiled = [re.compile(p, flags=re.IGNORECASE) for p in PATTERNS]

    bad = [
        "Как бы вы по-португальски мягко сказали продавцу...",
        "Чем в живой речи чаще заменяют habitação...",
        "Как в живой речи чаще просят чек...",
        "Как по-португальски вежливо уточнить срок...",
    ]
    for text in bad:
        assert any(p.search(text) for p in compiled)

    good = [
        "Как здесь правильно спросить, если сотрудник намекает...",
        "В какой форме лучше спросить, если нужно уточнить дедлайн...",
        "Что обычно говорят, когда после жалобы на поломку нужно...",
    ]
    for text in good:
        assert not any(p.search(text) for p in compiled)
