from __future__ import annotations

import sqlite3

from services.cat_runtime import (
    CATItemModel,
    load_cat_session_runtime,
    route_vocab_runtime_cat_answer,
    route_vocab_runtime_cat_start,
)


def _conn() -> sqlite3.Connection:
    return sqlite3.connect(":memory:")


def _item(item_id: int, difficulty_b: float = 0.0) -> CATItemModel:
    return CATItemModel(
        item_id=item_id,
        mode="vocab",
        modality="mcq",
        prompt_text=f"prompt-{item_id}",
        answer_key=f"answer-{item_id}",
        difficulty_b=difficulty_b,
        discrimination_a=1.0,
        guessing_c=0.2,
        upper_d=0.95,
        cefr_target="A2",
        content_tag="core",
        skill_tag="lexis",
        is_active=True,
    )


def test_route_vocab_runtime_cat_start_returns_noop_when_disabled() -> None:
    conn = _conn()
    try:
        result = route_vocab_runtime_cat_start(
            conn,
            user_id=1,
            attempt_id=2,
            feature_enabled=False,
            item_bank=[_item(10), _item(20)],
        )
        assert result.use_cat is False
        assert result.reason == "feature_disabled"
        assert result.route == "noop"
        assert result.result is None
    finally:
        conn.close()


def test_route_vocab_runtime_cat_start_starts_when_enabled() -> None:
    conn = _conn()
    try:
        bank = [_item(10, -0.3), _item(20, 0.2)]
        result = route_vocab_runtime_cat_start(
            conn,
            user_id=123,
            attempt_id=777,
            feature_enabled=True,
            item_bank=bank,
            started_at="2026-03-21T14:10:00Z",
            metadata={"source": "router-test"},
        )
        assert result.use_cat is True
        assert result.reason is None
        assert result.route == "start"
        assert result.result is not None
        assert result.result.cat_started is not None
        assert result.result.cat_started.step.action == "ask"

        loaded = load_cat_session_runtime(conn, session_id="cat:vocab:u123:a777")
        assert loaded is not None
        assert loaded.metadata["attempt_id"] == 777
        assert loaded.metadata["source"] == "router-test"
    finally:
        conn.close()


def test_route_vocab_runtime_cat_answer_returns_noop_when_disabled() -> None:
    conn = _conn()
    try:
        result = route_vocab_runtime_cat_answer(
            conn,
            user_id=1,
            attempt_id=2,
            feature_enabled=False,
            item=_item(10),
            response_value=1,
            is_correct=True,
            item_bank=[_item(10), _item(20)],
        )
        assert result.use_cat is False
        assert result.reason == "feature_disabled"
        assert result.route == "noop"
        assert result.result is None
    finally:
        conn.close()


def test_route_vocab_runtime_cat_answer_routes_to_existing_cat_session() -> None:
    conn = _conn()
    try:
        bank = [_item(10, -0.3), _item(20, 0.2), _item(30, 0.8)]

        started = route_vocab_runtime_cat_start(
            conn,
            user_id=123,
            attempt_id=778,
            feature_enabled=True,
            item_bank=bank,
            started_at="2026-03-21T14:11:00Z",
        )
        assert started.result is not None
        first_item = started.result.cat_started.step.next_item
        assert first_item is not None

        answered = route_vocab_runtime_cat_answer(
            conn,
            user_id=123,
            attempt_id=778,
            feature_enabled=True,
            item=first_item,
            response_value=1,
            is_correct=True,
            item_bank=bank,
            updated_at="2026-03-21T14:12:00Z",
        )
        assert answered.use_cat is True
        assert answered.route == "answer"
        assert answered.result is not None
        assert answered.result.action in {"ask", "stop"}

        loaded = load_cat_session_runtime(conn, session_id="cat:vocab:u123:a778")
        assert loaded is not None
        assert loaded.items_administered == [int(first_item.item_id)]
        assert len(loaded.answers) == 1
    finally:
        conn.close()
