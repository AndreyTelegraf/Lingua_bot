from __future__ import annotations

import sqlite3

from services.cat_runtime import (
    CATItemModel,
    build_vocab_cat_handoff,
    load_cat_session_runtime,
    start_vocab_cat_handoff,
    answer_vocab_cat_handoff,
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


def test_build_vocab_cat_handoff_is_deterministic() -> None:
    h1 = build_vocab_cat_handoff(user_id=123, attempt_id=555)
    h2 = build_vocab_cat_handoff(user_id=123, attempt_id=555)

    assert h1.session_id == h2.session_id
    assert h1.mode == "vocab"
    assert h1.metadata["attempt_id"] == 555
    assert h1.metadata["user_id"] == 123


def test_start_vocab_cat_handoff_delegates_to_bridge_runtime() -> None:
    conn = _conn()
    try:
        bank = [_item(10, -0.3), _item(20, 0.2)]

        started = start_vocab_cat_handoff(
            conn,
            user_id=123,
            attempt_id=777,
            feature_enabled=True,
            item_bank=bank,
            started_at="2026-03-21T13:30:00Z",
            metadata={"source": "handoff-test"},
        )

        assert started is not None
        assert started.session.session_id == "cat:vocab:u123:a777"
        assert started.step.action == "ask"

        loaded = load_cat_session_runtime(conn, session_id="cat:vocab:u123:a777")
        assert loaded is not None
        assert loaded.metadata["attempt_id"] == 777
        assert loaded.metadata["source"] == "handoff-test"
    finally:
        conn.close()


def test_answer_vocab_cat_handoff_routes_to_existing_session() -> None:
    conn = _conn()
    try:
        bank = [_item(10, -0.3), _item(20, 0.2), _item(30, 0.8)]

        started = start_vocab_cat_handoff(
            conn,
            user_id=123,
            attempt_id=778,
            feature_enabled=True,
            item_bank=bank,
        )
        assert started is not None
        first_item = started.step.next_item
        assert first_item is not None

        step = answer_vocab_cat_handoff(
            conn,
            user_id=123,
            attempt_id=778,
            item=first_item,
            response_value=1,
            is_correct=True,
            item_bank=bank,
            updated_at="2026-03-21T13:31:00Z",
        )

        assert step.action in {"ask", "stop"}

        loaded = load_cat_session_runtime(conn, session_id="cat:vocab:u123:a778")
        assert loaded is not None
        assert loaded.items_administered == [int(first_item.item_id)]
        assert len(loaded.answers) == 1
    finally:
        conn.close()


def test_start_vocab_cat_handoff_returns_none_when_feature_disabled() -> None:
    conn = _conn()
    try:
        bank = [_item(10), _item(20)]
        started = start_vocab_cat_handoff(
            conn,
            user_id=1,
            attempt_id=1,
            feature_enabled=False,
            item_bank=bank,
        )
        assert started is None
    finally:
        conn.close()
