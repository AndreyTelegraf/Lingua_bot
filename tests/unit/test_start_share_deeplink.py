from bot.common_handlers.start import _share_vocab_range_from_code, _build_inline_share_message


def test_share_vocab_range_from_code():
    assert _share_vocab_range_from_code("2500") == "1500–2500"
    assert _share_vocab_range_from_code("8000") == "6000–8000"


def test_build_inline_share_message():
    text = _build_inline_share_message("8000")
    assert "🇵🇹 ЯзыкоБот оценил мой словарный запас португальского в *6000–8000 слов*." in text
    assert "Проверьте себя через [ЯзыкоБот](https://t.me/lin_gua_bot?start=sv_8000)" in text
