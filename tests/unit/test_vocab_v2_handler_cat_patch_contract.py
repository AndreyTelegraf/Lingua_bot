from __future__ import annotations

from dataclasses import dataclass

from handlers import vocab_v2 as hv2


@dataclass
class _Route:
    source: str
    route_result: object | None = None


class _Store:
    def __init__(self) -> None:
        self.data = {}

    def get(self, *, user_id: int):
        return self.data.get(user_id)

    def set(self, *, user_id: int, fsm) -> None:
        self.data[user_id] = fsm

    def clear(self, *, user_id: int) -> None:
        self.data.pop(user_id, None)


def test_vocab_v2_start_marks_cat_branch_when_cat_route_present(monkeypatch) -> None:
    store = _Store()

    monkeypatch.setattr(
        hv2,
        "handle_vocab_start",
        lambda **kwargs: {
            "ok": True,
            "text": "started",
            "keyboard": [],
            "finished": False,
            "fsm": {"s": 1},
            "cat_route": _Route(source="cat", route_result={"route": "start"}),
        },
    )

    out = hv2.vocab_v2_start(conn="CONN", store=store, user_id=123)

    assert out["runtime_branch"] == "cat"
    assert store.get(user_id=123) == {"s": 1}


def test_vocab_v2_start_marks_legacy_when_no_cat_route(monkeypatch) -> None:
    store = _Store()

    monkeypatch.setattr(
        hv2,
        "handle_vocab_start",
        lambda **kwargs: {
            "ok": True,
            "text": "started",
            "keyboard": [],
            "finished": False,
            "fsm": {"s": 1},
        },
    )

    out = hv2.vocab_v2_start(conn="CONN", store=store, user_id=123)

    assert out["runtime_branch"] == "legacy"
    assert store.get(user_id=123) == {"s": 1}


def test_vocab_v2_callback_marks_cat_branch_and_persists_fsm(monkeypatch) -> None:
    store = _Store()
    store.set(user_id=123, fsm={"prev": 1})

    monkeypatch.setattr(
        hv2,
        "handle_vocab_callback",
        lambda **kwargs: {
            "ok": True,
            "text": "next",
            "keyboard": [],
            "finished": False,
            "fsm": {"next": 2},
            "cat_route": _Route(source="cat", route_result={"route": "answer"}),
        },
    )

    out = hv2.vocab_v2_callback(conn="CONN", store=store, user_id=123, callback_data="vocab:pick:1")

    assert out["runtime_branch"] == "cat"
    assert store.get(user_id=123) == {"next": 2}


def test_vocab_v2_callback_clears_store_when_finished(monkeypatch) -> None:
    store = _Store()
    store.set(user_id=123, fsm={"prev": 1})

    monkeypatch.setattr(
        hv2,
        "handle_vocab_callback",
        lambda **kwargs: {
            "ok": True,
            "text": "done",
            "keyboard": [],
            "finished": True,
            "fsm": {"done": 1},
        },
    )

    out = hv2.vocab_v2_callback(conn="CONN", store=store, user_id=123, callback_data="vocab:pick:1")

    assert out["runtime_branch"] == "legacy"
    assert store.get(user_id=123) is None


def test_vocab_v2_callback_returns_legacy_on_missing_fsm() -> None:
    store = _Store()

    out = hv2.vocab_v2_callback(conn="CONN", store=store, user_id=123, callback_data="vocab:pick:1")

    assert out["ok"] is False
    assert out["runtime_branch"] == "legacy"
