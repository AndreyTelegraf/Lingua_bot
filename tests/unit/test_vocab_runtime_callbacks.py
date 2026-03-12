from services.vocab_runtime.callbacks import decode_choice_callback, encode_choice_callback


def test_encode_choice_callback() -> None:
    assert encode_choice_callback(choice_id=101) == 'vocab:pick:101'


def test_decode_choice_callback_happy_path() -> None:
    assert decode_choice_callback('vocab:pick:101') == 101


def test_decode_choice_callback_rejects_bad_format() -> None:
    try:
        decode_choice_callback('vocab:pick')
        assert False, 'expected RuntimeError'
    except RuntimeError as e:
        assert str(e) == 'invalid_callback_format'


def test_decode_choice_callback_rejects_bad_prefix() -> None:
    try:
        decode_choice_callback('foo:pick:101')
        assert False, 'expected RuntimeError'
    except RuntimeError as e:
        assert str(e) == 'invalid_callback_prefix'


def test_decode_choice_callback_rejects_bad_choice_id() -> None:
    try:
        decode_choice_callback('vocab:pick:abc')
        assert False, 'expected RuntimeError'
    except RuntimeError as e:
        assert str(e) == 'invalid_callback_choice_id'
