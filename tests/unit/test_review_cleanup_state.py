from bot.common_handlers.start import (
    set_last_review_message_id,
    pop_last_review_message_id,
)


def test_review_state_roundtrip():
    set_last_review_message_id(100, 555)

    assert pop_last_review_message_id(100) == 555
    assert pop_last_review_message_id(100) is None


def test_review_state_override():
    set_last_review_message_id(200, 111)
    set_last_review_message_id(200, 222)

    assert pop_last_review_message_id(200) == 222


def test_review_state_clear():
    set_last_review_message_id(300, 999)
    set_last_review_message_id(300, None)

    assert pop_last_review_message_id(300) is None
