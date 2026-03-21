from __future__ import annotations

import sqlite3

from services.cat_runtime import CATItemModel, load_cat_session_runtime
from services.vocab_runtime.service import (
    maybe_continue_cat_from_vocab_service_answer,
    maybe_start_cat_from_vocab_service,
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


def test_vocab_service_cat_start_returns_legacy_when_disabled() -> None:
    conn = _conn()
    try:
        r = maybe_start_cat_from_vocab_service(
            conn,
            user_id=1,
            attempt_id=2,
            feature_enabled=False,
            item_bank=[_item(10), _item(20)],
        )
        assert r.use_cat is False
        assert r.source == "legacy"
        assert r.route_result is not None
        assert r.route_result.route == "noop"
    finally:
        conn.close()


def test_vocab_service_cat_start_routes_to_cat_when_enabled() -> None:
    conn = _conn()
    try:
        bank = [_item(10, -0.3), _item(20, 0.2)]
        r = maybe_start_cat_from_vocab_service(
            conn,
            user_id=123,
            attempt_id=777,
            feature_enabled=True,
            item_bank=bank,
            started_at="2026-03-21T14:40:00Z",
            metadata={"source": "service-cat-test"},
        )
        assert r.use_cat is True
        assert r.source == "cat"
        loaded = load_cat_session_runtime(conn, session_id="cat:vocab:u123:a777")
        assert loaded is not None
        assert loaded.metadata["source"] == "service-cat-test"
    finally:
        conn.close()


def test_vocab_service_cat_answer_continues_existing_cat_session() -> None:
    conn = _conn()
    try:
        bank = [_item(10, -0.3), _item(20, 0.2), _item(30, 0.8)]

        started = maybe_start_cat_from_vocab_service(
            conn,
            user_id=123,
            attempt_id=778,
            feature_enabled=True,
            item_bank=bank,
        )
        first_item = started.route_result.result.cat_started.step.next_item
        assert first_item is not None

        r = maybe_continue_cat_from_vocab_service_answer(
            conn,
            user_id=123,
            attempt_id=778,
            feature_enabled=True,
            item=first_item,
            response_value=1,
            is_correct=True,
            item_bank=bank,
            updated_at="2026-03-21T14:41:00Z",
        )
        assert r.use_cat is True
        assert r.source == "cat"

        loaded = load_cat_session_runtime(conn, session_id="cat:vocab:u123:a778")
        assert loaded is not None
        assert loaded.items_administered == [int(first_item.item_id)]
        assert len(loaded.answers) == 1
    finally:
        conn.close()
