from __future__ import annotations

from dataclasses import dataclass

from services.cat_runtime import CATItemModel
from services.vocab_runtime import flow as vf


@dataclass
class _Route:
    source: str
    route_result: object | None = None


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


def test_start_flow_branches_to_cat_when_service_returns_cat_route(monkeypatch) -> None:
    monkeypatch.setattr(
        "services.vocab_runtime.service.start_or_resume_attempt",
        lambda *args, **kwargs: {
            "attempt_id": 777,
            "user_id": 123,
            "cat_route": _Route(source="cat", route_result={"route": "start"}),
        },
    )
    monkeypatch.setattr(
        "services.vocab_runtime.service.get_next_question",
        lambda *args, **kwargs: {
            "attempt_id": 777,
            "item_id": 10,
            "cat_route": _Route(source="cat", route_result={"route": "question"}),
        },
    )

    result = vf.start_flow("CONN", user_id=123, cat_feature_enabled=True)

    assert result["attempt"]["mode"] == "cat"
    assert result["question"]["mode"] == "cat"
    assert result["attempt"]["cat_source"] == "cat"
    assert result["question"]["cat_source"] == "cat"


def test_start_flow_stays_legacy_without_cat_route(monkeypatch) -> None:
    monkeypatch.setattr(
        "services.vocab_runtime.service.start_or_resume_attempt",
        lambda *args, **kwargs: {"attempt_id": 1, "user_id": 2},
    )
    monkeypatch.setattr(
        "services.vocab_runtime.service.get_next_question",
        lambda *args, **kwargs: {"attempt_id": 1, "item_id": 10},
    )

    result = vf.start_flow("CONN", user_id=2, cat_feature_enabled=False)

    assert result["attempt"]["mode"] == "legacy"
    assert result["question"]["mode"] == "legacy"


def test_answer_flow_branches_to_cat_for_choice_path(monkeypatch) -> None:
    item = _item(10, -0.3)

    monkeypatch.setattr(
        "services.vocab_runtime.service.submit_choice",
        lambda *args, **kwargs: {
            "attempt_id": 778,
            "selected_answer": "house",
            "cat_route": _Route(source="cat", route_result={"route": "answer"}),
        },
    )

    result = vf.answer_flow(
        "CONN",
        user_id=123,
        attempt_id=778,
        item_id=10,
        choice_id=99,
        cat_feature_enabled=True,
        item=item,
    )

    assert result["mode"] == "cat"
    assert result["cat_source"] == "cat"
    assert result["result"]["selected_answer"] == "house"


def test_answer_flow_branches_to_legacy_for_text_path_without_cat(monkeypatch) -> None:
    monkeypatch.setattr(
        "services.vocab_runtime.service.submit_answer",
        lambda *args, **kwargs: {
            "attempt_id": 779,
            "is_correct": True,
        },
    )

    result = vf.answer_flow(
        "CONN",
        user_id=123,
        attempt_id=779,
        item_id=10,
        answer_text="house",
        cat_feature_enabled=False,
    )

    assert result["mode"] == "legacy"
    assert result["result"]["is_correct"] is True
