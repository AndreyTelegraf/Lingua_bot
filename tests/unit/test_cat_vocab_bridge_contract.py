from __future__ import annotations

import sqlite3

from services.cat_runtime import (
    CATItemModel,
    answer_mode_cat_bridge,
    build_cat_session_id,
    cat_feature_enabled,
    load_cat_session_runtime,
    should_use_cat_for_mode,
    start_mode_cat_bridge,
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


def test_cat_feature_enabled_parses_common_truthy_values() -> None:
    assert cat_feature_enabled("1") is True
    assert cat_feature_enabled("true") is True
    assert cat_feature_enabled("yes") is True
    assert cat_feature_enabled("on") is True
    assert cat_feature_enabled("0") is False
    assert cat_feature_enabled(None) is False


def test_should_use_cat_for_mode_blocks_when_flag_off() -> None:
    d = should_use_cat_for_mode(mode="vocab", feature_enabled=False)
    assert d.enabled is False
    assert d.reason == "feature_disabled"


def test_should_use_cat_for_mode_blocks_unsupported_mode() -> None:
    d = should_use_cat_for_mode(mode="level", feature_enabled=True)
    assert d.enabled is False
    assert d.reason == "mode_not_supported"


def test_build_cat_session_id_is_stable() -> None:
    assert build_cat_session_id(user_id=123, mode="vocab", attempt_id=77) == "cat:vocab:u123:a77"
    assert build_cat_session_id(user_id=123, mode="vocab") == "cat:vocab:u123"


def test_start_mode_cat_bridge_returns_none_when_disabled() -> None:
    conn = _conn()
    try:
        bank = [_item(10), _item(20)]
        started = start_mode_cat_bridge(
            conn,
            user_id=123,
            mode="vocab",
            feature_enabled=False,
            item_bank=bank,
            attempt_id=555,
        )
        assert started is None
    finally:
        conn.close()


def test_start_mode_cat_bridge_starts_repo_backed_runtime_when_enabled() -> None:
    conn = _conn()
    try:
        bank = [_item(10, -0.4), _item(20, 0.1), _item(30, 0.7)]
        started = start_mode_cat_bridge(
            conn,
            user_id=123,
            mode="vocab",
            feature_enabled=True,
            item_bank=bank,
            attempt_id=555,
            started_at="2026-03-21T13:30:00Z",
            metadata={"source": "bridge-test"},
        )

        assert started is not None
        assert started.session.session_id == "cat:vocab:u123:a555"
        assert started.step.action in {"ask", "stop"}

        loaded = load_cat_session_runtime(conn, session_id="cat:vocab:u123:a555")
        assert loaded is not None
        assert loaded.metadata["bridge_mode"] == "vocab"
        assert loaded.metadata["attempt_id"] == 555
        assert loaded.metadata["source"] == "bridge-test"
    finally:
        conn.close()


def test_answer_mode_cat_bridge_uses_stable_session_id() -> None:
    conn = _conn()
    try:
        bank = [_item(10, -0.4), _item(20, 0.1), _item(30, 0.7)]
        started = start_mode_cat_bridge(
            conn,
            user_id=123,
            mode="vocab",
            feature_enabled=True,
            item_bank=bank,
            attempt_id=777,
        )
        assert started is not None
        assert started.step.next_item is not None

        step = answer_mode_cat_bridge(
            conn,
            user_id=123,
            mode="vocab",
            attempt_id=777,
            item=started.step.next_item,
            response_value=1,
            is_correct=True,
            item_bank=bank,
            updated_at="2026-03-21T13:31:00Z",
        )

        assert step.action in {"ask", "stop"}

        loaded = load_cat_session_runtime(conn, session_id="cat:vocab:u123:a777")
        assert loaded is not None
        assert len(loaded.answers) == 1
        assert loaded.items_administered == [started.step.next_item.item_id]
    finally:
        conn.close()


def test_answer_mode_cat_bridge_raises_when_session_missing() -> None:
    conn = _conn()
    try:
        bank = [_item(10), _item(20)]
        try:
            answer_mode_cat_bridge(
                conn,
                user_id=123,
                mode="vocab",
                attempt_id=999,
                item=bank[0],
                response_value=1,
                is_correct=True,
                item_bank=bank,
            )
        except ValueError as exc:
            assert "cat bridge session not found" in str(exc)
        else:
            raise AssertionError("expected ValueError for missing bridge session")
    finally:
        conn.close()
