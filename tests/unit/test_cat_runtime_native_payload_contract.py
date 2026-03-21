from __future__ import annotations

import sqlite3

from services.cat_runtime import (
    CATItemModel,
    build_cat_runtime_native_payload,
    load_cat_session_runtime,
    start_cat_session_runtime_native,
    answer_cat_session_runtime_native,
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


def test_start_runtime_native_returns_question_payload() -> None:
    conn = _conn()
    try:
        bank = [_item(10, -0.3), _item(20, 0.2)]
        started = start_cat_session_runtime_native(
            conn,
            session_id="sess-native-1",
            user_id=123,
            modality="vocab",
            item_bank=bank,
            started_at="2026-03-21T15:20:00Z",
        )

        assert started.payload.kind == "question"
        assert started.payload.mode == "vocab"
        assert started.payload.session_id == "sess-native-1"
        assert started.payload.item_id is not None
        assert started.payload.prompt_text is not None
        assert started.payload.answer_key is not None
        assert started.payload.stop_reason is None
        assert started.payload.payload_version == "cat_runtime_payload_v1"
    finally:
        conn.close()


def test_answer_runtime_native_returns_question_or_result_payload() -> None:
    conn = _conn()
    try:
        bank = [_item(10, -0.3), _item(20, 0.2), _item(30, 0.8)]
        started = start_cat_session_runtime_native(
            conn,
            session_id="sess-native-2",
            user_id=123,
            modality="vocab",
            item_bank=bank,
        )
        first_item = started.step.next_item
        assert first_item is not None

        answered = answer_cat_session_runtime_native(
            conn,
            session_id="sess-native-2",
            item=first_item,
            response_value=1,
            is_correct=True,
            item_bank=bank,
            updated_at="2026-03-21T15:21:00Z",
        )

        assert answered.payload.kind in {"question", "result"}
        assert answered.payload.mode == "vocab"
        assert answered.payload.session_id == "sess-native-2"
        loaded = load_cat_session_runtime(conn, session_id="sess-native-2")
        assert loaded is not None
        assert loaded.items_administered == [int(first_item.item_id)]
    finally:
        conn.close()


def test_build_native_payload_for_stop_step_returns_result_kind() -> None:
    conn = _conn()
    try:
        bank = [_item(10, -0.3)]
        started = start_cat_session_runtime_native(
            conn,
            session_id="sess-native-3",
            user_id=123,
            modality="vocab",
            item_bank=bank,
        )
        first_item = started.step.next_item
        assert first_item is not None

        answered = answer_cat_session_runtime_native(
            conn,
            session_id="sess-native-3",
            item=first_item,
            response_value=1,
            is_correct=True,
            item_bank=bank,
        )

        if answered.step.action == "stop":
            assert answered.payload.kind == "result"
        else:
            rebuilt = build_cat_runtime_native_payload(
                session=answered.session,
                step=answered.step,
                mode="vocab",
            )
            assert rebuilt.kind == "question"
    finally:
        conn.close()
