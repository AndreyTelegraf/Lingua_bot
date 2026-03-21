from services.cat_runtime import (
    CATItemModel,
    CATEstimate,
    append_answer,
    create_cat_session,
    finish_cat_session,
    restore_cat_session,
    serialize_cat_session,
)


def _item(item_id: int) -> CATItemModel:
    return CATItemModel(
        item_id=item_id,
        mode="vocab",
        modality="mcq",
        prompt_text=f"prompt {item_id}",
        answer_key=f"answer_{item_id}",
        difficulty_b=0.0,
        discrimination_a=1.0,
        guessing_c=0.2,
        upper_d=0.95,
        cefr_target="A2",
    )


def test_create_session_defaults() -> None:
    s = create_cat_session(
        session_id="sess-1",
        user_id=123,
        modality="vocab",
        started_at="2026-03-21T11:00:00Z",
    )
    assert s.session_id == "sess-1"
    assert s.user_id == 123
    assert s.modality == "vocab"
    assert s.theta == 0.0
    assert s.se is None
    assert s.questions_answered == 0
    assert s.status == "in_progress"


def test_append_answer_updates_state_and_history() -> None:
    s = create_cat_session(session_id="sess-1", user_id=123, modality="vocab")
    est = CATEstimate(theta=0.42, se=0.31, information=10.4, items_answered=1, converged=True)

    append_answer(
        s,
        item=_item(10),
        response_value=1,
        is_correct=True,
        estimate_after=est,
        updated_at="2026-03-21T11:05:00Z",
    )

    assert s.items_administered == [10]
    assert s.questions_answered == 1
    assert s.theta == 0.42
    assert s.se == 0.31
    assert s.updated_at == "2026-03-21T11:05:00Z"
    assert s.answers[0].theta_before == 0.0
    assert s.answers[0].theta_after == 0.42


def test_append_answer_rejects_duplicate_item() -> None:
    s = create_cat_session(session_id="sess-1", user_id=123, modality="vocab")
    append_answer(s, item=_item(10), response_value=1, is_correct=True)

    try:
        append_answer(s, item=_item(10), response_value=0, is_correct=False)
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "item already administered" in str(exc)


def test_finish_session_sets_status_and_final_estimate() -> None:
    s = create_cat_session(session_id="sess-1", user_id=123, modality="vocab")
    final_est = CATEstimate(theta=-0.2, se=0.28, information=12.0, items_answered=1, converged=True)

    finish_cat_session(
        s,
        final_estimate=final_est,
        finished_at="2026-03-21T11:15:00Z",
        reason="target_precision_reached",
    )

    assert s.status == "finished"
    assert s.theta == -0.2
    assert s.se == 0.28
    assert s.updated_at == "2026-03-21T11:15:00Z"
    assert s.metadata["finish_reason"] == "target_precision_reached"


def test_serialize_restore_roundtrip() -> None:
    s = create_cat_session(
        session_id="sess-1",
        user_id=123,
        modality="vocab",
        started_at="2026-03-21T11:00:00Z",
        metadata={"source": "test"},
    )
    est = CATEstimate(theta=0.55, se=0.22, information=20.0, items_answered=1, converged=True)
    append_answer(s, item=_item(10), response_value=1, is_correct=True, estimate_after=est)
    payload = serialize_cat_session(s)
    restored = restore_cat_session(payload)

    assert restored.session_id == s.session_id
    assert restored.user_id == s.user_id
    assert restored.modality == s.modality
    assert restored.items_administered == s.items_administered
    assert restored.questions_answered == s.questions_answered
    assert restored.theta == s.theta
    assert restored.se == s.se
    assert restored.metadata == s.metadata
    assert restored.answers[0].item_id == 10
    assert restored.answers[0].theta_after == 0.55
