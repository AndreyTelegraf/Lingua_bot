from bot.common_handlers.start import _share_vocab_range_from_code, _build_inline_share_message


def test_share_vocab_range_from_code():
    assert _share_vocab_range_from_code("2500") == "1 500–2 500"
    assert _share_vocab_range_from_code("8000") == "8000+"


def test_build_inline_share_message():
    text = _build_inline_share_message("8000")
    assert "🇵🇹 ЯзыкоБот оценил мой словарный запас португальского в *8000+ слов*." in text
    assert "Проверьте себя через [ЯзыкоБот](https://t.me/lin_gua_bot?start=sv_8000)" in text


def test_share_vocab_range_from_code_additional():
    assert _share_vocab_range_from_code("1500") == "1 000–1 500"
    assert _share_vocab_range_from_code("4000") == "2 500–4 000"
    assert _share_vocab_range_from_code("6000") == "4 000–6 000"


def test_share_vocab_range_from_code_low_bands():
    assert _share_vocab_range_from_code("500") == "<500"
    assert _share_vocab_range_from_code("1000") == "500–1 000"
    assert _share_vocab_range_from_code("1500") == "1 000–1 500"
