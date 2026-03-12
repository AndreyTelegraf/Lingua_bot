from services.vocab_runtime.aiogram_mapper import map_answer_result, map_start_result


class DummyFSM:
    pass


def test_map_start_result() -> None:
    fsm = DummyFSM()
    view = {'item_id': 1, 'text': 'casa'}
    out = map_start_result((fsm, view))
    assert out['fsm'] is fsm
    assert out['view'] == view


def test_map_answer_result() -> None:
    fsm = DummyFSM()
    payload = {
        'answer_result': {'is_correct': True},
        'next_view': {'item_id': 2},
    }
    out = map_answer_result((fsm, payload))
    assert out['fsm'] is fsm
    assert out['answer_result']['is_correct'] is True
    assert out['next_view']['item_id'] == 2
