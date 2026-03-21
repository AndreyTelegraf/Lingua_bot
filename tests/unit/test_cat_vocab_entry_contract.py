from __future__ import annotations

import sqlite3

from services.cat_runtime import (
    CATItemModel,
    decide_vocab_cat_entry,
    load_cat_session_runtime,
    start_vocab_runtime_cat_entry,
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


def test_decide_vocab_cat_entry_returns_disabled_when_flag_off() -> None:
    d = decide_vocab_cat_entry(
        user_id=123,
        attempt_id=456,
        feature_enabled=False,
    )
    assert d.use_cat is False
    assert d.reason == "feature_disabled"
    assert d.handoff is None


def test_decide_vocab_cat_entry_builds_handoff_when_enabled() -> None:
    d = decide_vocab_cat_entry(
        user_id=123,
        attempt_id=456,
        feature_enabled=True,
        metadata={"source": "entry-test"},
    )
    assert d.use_cat is True
    assert d.reason is None
    assert d.handoff is not None
    assert d.handoff.session_id == "cat:vocab:u123:a456"
    assert d.handoff.metadata["attempt_id"] == 456
    assert d.handoff.metadata["source"] == "entry-test"


def test_start_vocab_runtime_cat_entry_returns_noop_when_disabled() -> None:
    conn = _conn()
    try:
        result = start_vocab_runtime_cat_entry(
            conn,
            user_id=1,
            attempt_id=2,
            feature_enabled=False,
            item_bank=[_item(10), _item(20)],
        )
        assert result.decision.use_cat is False
        assert result.cat_started is None
    finally:
        conn.close()


def test_start_vocab_runtime_cat_entry_starts_cat_when_enabled() -> None:
    conn = _conn()
    try:
        bank = [_item(10, -0.3), _item(20, 0.2)]
        result = start_vocab_runtime_cat_entry(
            conn,
            user_id=123,
            attempt_id=777,
            feature_enabled=True,
            item_bank=bank,
            started_at="2026-03-21T13:50:00Z",
            metadata={"source": "entry-test"},
        )
        assert result.decision.use_cat is True
        assert result.decision.handoff is not None
        assert result.cat_started is not None
        assert result.cat_started.step.action == "ask"

        loaded = load_cat_session_runtime(conn, session_id="cat:vocab:u123:a777")
        assert loaded is not None
        assert loaded.metadata["attempt_id"] == 777
        assert loaded.metadata["source"] == "entry-test"
    finally:
        conn.close()
