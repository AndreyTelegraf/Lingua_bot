from __future__ import annotations

from services.cat_runtime import CATItemModel
from services.vocab_runtime import service as svc


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


def test_start_or_resume_attempt_adds_cat_route_when_enabled(monkeypatch) -> None:
    seen = {}

    def fake_legacy(conn, *, user_id):
        seen["legacy"] = {"conn": conn, "user_id": user_id}
        return {"attempt_id": 777, "user_id": user_id, "status": "started"}

    def fake_cat(conn, **kwargs):
        seen["cat"] = {"conn": conn, **kwargs}
        return {"route": "cat-started"}

    monkeypatch.setattr(svc, "_start_or_resume_attempt_legacy", fake_legacy)
    monkeypatch.setattr(svc, "maybe_start_cat_from_vocab_service", fake_cat)

    result = svc.start_or_resume_attempt(
        "CONN",
        user_id=123,
        cat_feature_enabled=True,
        metadata={"source": "layer20"},
    )

    assert result["attempt_id"] == 777
    assert result["cat_route"]["route"] == "cat-started"
    assert seen["cat"]["attempt_id"] == 777
    assert seen["cat"]["user_id"] == 123


def test_get_next_question_adds_cat_route_when_enabled(monkeypatch) -> None:
    seen = {}

    def fake_legacy(conn, *, user_id):
        seen["legacy"] = {"conn": conn, "user_id": user_id}
        return {"attempt_id": 778, "item_id": 10, "lemma": "casa", "question_text": "q", "correct_answer": "house", "pos": "noun"}

    def fake_cat(conn, **kwargs):
        seen["cat"] = {"conn": conn, **kwargs}
        return {"route": "cat-started"}

    monkeypatch.setattr(svc, "_get_next_question_legacy", fake_legacy)
    monkeypatch.setattr(svc, "maybe_start_cat_from_vocab_service", fake_cat)

    result = svc.get_next_question(
        "CONN",
        user_id=123,
        cat_feature_enabled=True,
    )

    assert result["item_id"] == 10
    assert result["cat_route"]["route"] == "cat-started"
    assert seen["cat"]["attempt_id"] == 778


def test_submit_choice_adds_cat_route_when_enabled(monkeypatch) -> None:
    seen = {}
    item = _item(10, -0.3)

    def fake_legacy(conn, *, user_id, attempt_id, item_id, choice_id):
        seen["legacy"] = {
            "conn": conn,
            "user_id": user_id,
            "attempt_id": attempt_id,
            "item_id": item_id,
            "choice_id": choice_id,
        }
        return {"attempt_id": attempt_id, "user_id": user_id, "is_correct": True, "selected_answer": "house"}

    def fake_cat(conn, **kwargs):
        seen["cat"] = {"conn": conn, **kwargs}
        return {"route": "cat-continued"}

    monkeypatch.setattr(svc, "_submit_choice_legacy", fake_legacy)
    monkeypatch.setattr(svc, "maybe_continue_cat_from_vocab_service_answer", fake_cat)

    result = svc.submit_choice(
        "CONN",
        user_id=123,
        attempt_id=778,
        item_id=10,
        choice_id=99,
        item=item,
        cat_feature_enabled=True,
    )

    assert result["selected_answer"] == "house"
    assert result["cat_route"]["route"] == "cat-continued"
    assert seen["cat"]["attempt_id"] == 778
    assert seen["cat"]["item"].item_id == 10


def test_wrappers_are_noop_when_disabled(monkeypatch) -> None:
    monkeypatch.setattr(
        svc,
        "_start_or_resume_attempt_legacy",
        lambda conn, *, user_id: {"attempt_id": 1, "user_id": user_id, "status": "legacy"},
    )
    monkeypatch.setattr(
        svc,
        "_submit_choice_legacy",
        lambda conn, *, user_id, attempt_id, item_id, choice_id: {"attempt_id": attempt_id, "user_id": user_id, "ok": True},
    )

    start_result = svc.start_or_resume_attempt("CONN", user_id=2, cat_feature_enabled=False)
    answer_result = svc.submit_choice(
        "CONN",
        user_id=2,
        attempt_id=1,
        item_id=10,
        choice_id=20,
        item=_item(10),
        cat_feature_enabled=False,
    )

    assert "cat_route" not in start_result
    assert "cat_route" not in answer_result
