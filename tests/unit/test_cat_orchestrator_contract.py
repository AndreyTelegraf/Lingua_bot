from __future__ import annotations

from dataclasses import dataclass

from services.cat_runtime import (
    CATItemModel,
    CATEstimate,
    CATOrchestrationStep,
    create_cat_session,
    plan_next_cat_step,
    record_answer_and_plan_next,
)


@dataclass(slots=True)
class _Stop:
    should_stop: bool
    reason: str | None
    questions_answered: int = 0
    min_questions: int = 8
    max_questions: int = 24
    current_se: float | None = None
    target_se: float | None = 0.35


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


def test_plan_next_cat_step_selects_item_for_active_session(monkeypatch) -> None:
    session = create_cat_session(session_id="sess-1", user_id=123, modality="vocab")
    session.theta = 0.25
    session.se = 0.40

    bank = [_item(1, -0.5), _item(2, 0.0), _item(3, 0.5)]
    seen: dict[str, object] = {}

    def fake_should_stop(**kwargs):
        seen["stop_kwargs"] = kwargs
        return _Stop(should_stop=False, reason=None, questions_answered=0, current_se=0.40)

    def fake_select(**kwargs):
        seen["select_kwargs"] = kwargs
        return bank[1]

    monkeypatch.setattr("services.cat_runtime.orchestrator.should_stop_cat", fake_should_stop)
    monkeypatch.setattr("services.cat_runtime.orchestrator.select_next_item_for_theta", fake_select)

    step = plan_next_cat_step(session, candidate_items=bank)

    assert isinstance(step, CATOrchestrationStep)
    assert step.action == "ask"
    assert step.next_item is not None
    assert step.next_item.item_id == 2
    assert step.estimate is not None
    assert step.estimate.theta == 0.25
    assert step.estimate.se == 0.40
    assert round(step.estimate.information, 2) == 6.25

    assert seen["stop_kwargs"]["questions_answered"] == 0
    assert seen["stop_kwargs"]["current_se"] == 0.40
    assert seen["select_kwargs"]["items"][1].item_id == 2
    assert seen["select_kwargs"]["theta"] == 0.25


def test_plan_next_cat_step_finishes_when_stopping_rule_triggers(monkeypatch) -> None:
    session = create_cat_session(session_id="sess-2", user_id=123, modality="vocab")
    session.theta = -0.10
    session.se = 0.18

    finished: dict[str, object] = {}

    def fake_should_stop(**kwargs):
        return _Stop(
            should_stop=True,
            reason="target_precision_reached",
            questions_answered=8,
            current_se=0.18,
        )

    def fake_finish(s, *, final_estimate=None, finished_at=None, reason=None):
        s.status = "finished"
        if final_estimate is not None:
            s.theta = final_estimate.theta
            s.se = final_estimate.se
        finished["reason"] = reason
        finished["final_estimate"] = final_estimate

    monkeypatch.setattr("services.cat_runtime.orchestrator.should_stop_cat", fake_should_stop)
    monkeypatch.setattr("services.cat_runtime.orchestrator.finish_cat_session", fake_finish)

    step = plan_next_cat_step(session, candidate_items=[_item(1)])

    assert step.action == "stop"
    assert step.next_item is None
    assert step.estimate is not None
    assert step.estimate.theta == -0.10
    assert step.estimate.se == 0.18
    assert session.status == "finished"
    assert session.theta == -0.10
    assert session.se == 0.18
    assert finished["reason"] == "target_precision_reached"
    assert finished["final_estimate"] is not None


def test_record_answer_and_plan_next_updates_session_and_returns_next_item(monkeypatch) -> None:
    session = create_cat_session(session_id="sess-3", user_id=777, modality="vocab")
    bank = [_item(10, -0.2), _item(20, 0.4)]
    new_est = CATEstimate(
        theta=0.61,
        se=0.27,
        information=13.7,
        items_answered=1,
        converged=True,
    )

    calls: dict[str, object] = {}

    def fake_build_responses(**kwargs):
        calls["build_responses"] = kwargs
        return [{"item_id": 10, "response_value": 1, "is_correct": True}]

    def fake_estimate(**kwargs):
        calls["estimate"] = kwargs
        return new_est

    def fake_should_stop(**kwargs):
        return _Stop(should_stop=False, reason=None, questions_answered=1, current_se=0.27)

    def fake_select(**kwargs):
        calls["select"] = kwargs
        return bank[1]

    monkeypatch.setattr("services.cat_runtime.orchestrator.build_cat_responses", fake_build_responses)
    monkeypatch.setattr("services.cat_runtime.orchestrator.estimate_from_items", fake_estimate)
    monkeypatch.setattr("services.cat_runtime.orchestrator.should_stop_cat", fake_should_stop)
    monkeypatch.setattr("services.cat_runtime.orchestrator.select_next_item_for_theta", fake_select)

    step = record_answer_and_plan_next(
        session,
        item=bank[0],
        response_value=1,
        is_correct=True,
        item_bank=bank,
        updated_at="2026-03-21T12:00:00Z",
    )

    assert step.action == "ask"
    assert step.next_item is not None
    assert step.next_item.item_id == 20
    assert session.theta == new_est.theta
    assert session.se == new_est.se
    assert calls["build_responses"]["answers"] == []
    assert calls["estimate"]["responses"][0]["item_id"] == 10
    assert calls["select"]["theta"] == 0.61
