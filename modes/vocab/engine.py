from __future__ import annotations

from aiogram.types import User as TgUser

from app.container import container
from domain.attempts.repository import FsmRuntimeRepository
from domain.shared.enums import AttemptStatus, ModeCode
from modes.vocab.dto import (
    VocabAbortResult,
    VocabFinishResult,
    VocabQuestion,
    VocabReportErrorResult,
    VocabStartResult,
    VocabSubmitAnswerResult,
    VocabSubmitDontKnowResult,
)
from modes.vocab.renderer import VocabRenderer
from modes.vocab.repo import VocabRepository
from modes.vocab.selector import VocabSelector
from services.vocab_runtime.scoring import build_scoring_input_from_events, score_attempt_v1


class VocabEngine:
    async def start_attempt(
        self,
        *,
        tg_user: TgUser,
        prior_payload: dict[str, object] | None = None,
    ) -> VocabStartResult:
        if container.db is None:
            raise RuntimeError("db_not_initialized")

        conn = container.db
        repo = VocabRepository(conn)
        fsm_repo = FsmRuntimeRepository(conn)

        await repo.seed_demo_items_if_empty()
        user_id = await repo.upsert_user_from_telegram(tg_user)

        existing = await repo.get_active_vocab_attempt(user_id=user_id)
        if existing is not None:
            raise RuntimeError("active_vocab_attempt_exists")

        mode_run_id = await repo.create_mode_run(user_id=user_id, prior_payload=prior_payload)
        vocab_attempt_id = await repo.create_vocab_attempt(mode_run_id=mode_run_id, user_id=user_id)

        await repo.append_attempt_event(
            attempt_id=vocab_attempt_id,
            user_id=user_id,
            event_type="attempt_started",
            step_index=0,
            payload={"mode_run_id": mode_run_id},
        )

        state = await fsm_repo.create_state(
            mode=ModeCode.VOCAB,
            user_id=user_id,
            run_id=mode_run_id,
            status=AttemptStatus.IDLE,
        )

        state = await fsm_repo.transition(
            mode=ModeCode.VOCAB,
            user_id=user_id,
            expected_revision=state.revision,
            target_status=AttemptStatus.SELECTING,
        )

        return VocabStartResult(
            mode_run_id=mode_run_id,
            vocab_attempt_id=vocab_attempt_id,
            current_step=state.current_step,
            status=state.status.value,
        )

    async def prepare_next_question(
        self,
        *,
        tg_user: TgUser,
    ) -> VocabQuestion:
        if container.db is None:
            raise RuntimeError("db_not_initialized")

        conn = container.db
        repo = VocabRepository(conn)
        fsm_repo = FsmRuntimeRepository(conn)
        selector = VocabSelector(conn)
        renderer = VocabRenderer(conn)

        user_id = await repo.upsert_user_from_telegram(tg_user)
        active = await repo.get_active_vocab_attempt(user_id=user_id)
        if active is None:
            raise RuntimeError("active_vocab_attempt_not_found")

        state = await fsm_repo.get_state(ModeCode.VOCAB, user_id)
        if state is None:
            raise RuntimeError("fsm_state_not_found_for_active_attempt")

        if state.status != AttemptStatus.SELECTING:
            raise RuntimeError(f"unexpected_fsm_status:{state.status.value}")

        picked = await selector.pick_next_item(attempt_id=int(active["id"]))
        if picked is None:
            raise RuntimeError("no_vocab_items_available")

        next_step = state.current_step + 1
        callback_token = f"v{int(active['id'])}:{next_step}:{int(picked['id'])}"
        payload = await renderer.build_question_payload(item_id=int(picked["id"]))

        prepared_state = await fsm_repo.transition(
            mode=ModeCode.VOCAB,
            user_id=user_id,
            expected_revision=state.revision,
            target_status=AttemptStatus.QUESTION_READY,
            current_item_id=str(int(picked["id"])),
            expected_callback_token=callback_token,
            increment_step=False,
        )

        selector_state = await repo.get_selector_state(attempt_id=int(active["id"]))
        selector_state.current_item_meta = {
            "item_id": int(picked["id"]),
            "pos": (picked["pos"] if "pos" in picked.keys() else None),
            "level": (picked["level"] if "level" in picked.keys() else None),
            "bin_name": (picked["bin_name"] if "bin_name" in picked.keys() else None),
            "step_index": next_step,
        }
        await repo.save_selector_state(
            attempt_id=int(active["id"]),
            state=selector_state,
        )

        await repo.update_selector_state(
            attempt_id=int(active["id"]),
            payload={
                "current_question": payload,
                "mode_run_id": int(active["mode_run_id"]),
                "step_index": next_step,
                "callback_token": callback_token,
            },
        )

        await repo.append_attempt_event(
            attempt_id=int(active["id"]),
            user_id=user_id,
            event_type="question_prepared",
            step_index=next_step,
            item_id=int(picked["id"]),
            payload={"mode_run_id": int(active["mode_run_id"])},
        )

        return VocabQuestion(
            mode_run_id=int(active["mode_run_id"]),
            vocab_attempt_id=int(active["id"]),
            step_index=next_step,
            item_id=int(picked["id"]),
            question_text=str(payload["question_text"]),
            choices=list(payload["choices"]),
            callback_token=callback_token,
        )

    async def confirm_question_shown(
        self,
        *,
        tg_user: TgUser,
        callback_token: str,
        message_id: int | None = None,
    ) -> None:
        if container.db is None:
            raise RuntimeError("db_not_initialized")

        conn = container.db
        repo = VocabRepository(conn)
        fsm_repo = FsmRuntimeRepository(conn)

        user_id = await repo.upsert_user_from_telegram(tg_user)
        active = await repo.get_active_vocab_attempt(user_id=user_id)
        if active is None:
            raise RuntimeError("active_vocab_attempt_not_found")

        state = await fsm_repo.get_state(ModeCode.VOCAB, user_id)
        if state is None:
            raise RuntimeError("fsm_state_not_found_for_active_attempt")

        if state.status != AttemptStatus.QUESTION_READY:
            raise RuntimeError(f"question_not_ready_for_show:{state.status.value}")

        if state.expected_callback_token != callback_token:
            raise RuntimeError("stale_callback_token")

        if state.current_item_id is None:
            raise RuntimeError("current_item_missing_for_question_show")

        item_id = int(state.current_item_id)
        next_step = state.current_step + 1

        selector_state = await repo.get_selector_state(attempt_id=int(active["id"]))
        current_meta = selector_state.current_item_meta or {}
        selector_state.mark_item_shown(
            item_id=item_id,
            pos=(str(current_meta["pos"]) if current_meta.get("pos") is not None else None),
            level=(str(current_meta["level"]) if current_meta.get("level") is not None else None),
            bin_name=(str(current_meta["bin_name"]) if current_meta.get("bin_name") is not None else None),
            step_index=next_step,
        )
        await repo.save_selector_state(
            attempt_id=int(active["id"]),
            state=selector_state,
        )

        await repo.increment_attempt_step(attempt_id=int(active["id"]))

        await repo.append_attempt_event(
            attempt_id=int(active["id"]),
            user_id=user_id,
            event_type="question_shown",
            step_index=next_step,
            item_id=item_id,
            payload={
                "mode_run_id": int(active["mode_run_id"]),
                "callback_token": callback_token,
                "message_id": message_id,
            },
        )

        await fsm_repo.transition(
            mode=ModeCode.VOCAB,
            user_id=user_id,
            expected_revision=state.revision,
            target_status=AttemptStatus.AWAITING_ANSWER,
            current_item_id=str(item_id),
            expected_callback_token=callback_token,
            expected_message_id=message_id,
            increment_step=True,
        )

    async def reject_prepared_question(
        self,
        *,
        tg_user: TgUser,
        callback_token: str,
        reason_code: str = "question_render_failed",
    ) -> None:
        if container.db is None:
            raise RuntimeError("db_not_initialized")

        conn = container.db
        repo = VocabRepository(conn)
        fsm_repo = FsmRuntimeRepository(conn)

        user_id = await repo.upsert_user_from_telegram(tg_user)
        active = await repo.get_active_vocab_attempt(user_id=user_id)
        if active is None:
            raise RuntimeError("active_vocab_attempt_not_found")

        state = await fsm_repo.get_state(ModeCode.VOCAB, user_id)
        if state is None:
            raise RuntimeError("fsm_state_not_found_for_active_attempt")

        if state.status != AttemptStatus.QUESTION_READY:
            raise RuntimeError(f"prepared_question_reject_not_allowed:{state.status.value}")

        if state.expected_callback_token != callback_token:
            raise RuntimeError("stale_callback_token")

        if state.current_item_id is None:
            raise RuntimeError("current_item_missing_for_prepared_reject")

        item_id = int(state.current_item_id)
        prepared_step = state.current_step + 1

        selector_state = await repo.get_selector_state(attempt_id=int(active["id"]))
        if item_id not in selector_state.shown_item_ids:
            selector_state.shown_item_ids.append(item_id)
        selector_state.clear_current_item()
        await repo.save_selector_state(
            attempt_id=int(active["id"]),
            state=selector_state,
        )

        selector_payload = await repo.get_selector_payload_state(attempt_id=int(active["id"]))
        selector_payload.pop("current_question", None)
        selector_payload.pop("callback_token", None)
        selector_payload["last_reject"] = {
            "item_id": item_id,
            "reason_code": reason_code,
            "callback_token": callback_token,
            "step_index": prepared_step,
        }
        await repo.update_selector_state(
            attempt_id=int(active["id"]),
            payload=selector_payload,
        )

        await repo.bump_attempt_reject(attempt_id=int(active["id"]))

        await repo.append_attempt_event(
            attempt_id=int(active["id"]),
            user_id=user_id,
            event_type="question_render_failed",
            step_index=prepared_step,
            item_id=item_id,
            reason_code=reason_code,
            payload={
                "mode_run_id": int(active["mode_run_id"]),
                "callback_token": callback_token,
            },
        )

        await fsm_repo.transition(
            mode=ModeCode.VOCAB,
            user_id=user_id,
            expected_revision=state.revision,
            target_status=AttemptStatus.SELECTING,
            current_item_id=None,
            expected_callback_token=None,
            expected_message_id=None,
            increment_step=False,
        )

    async def submit_answer(
        self,
        *,
        tg_user: TgUser,
        selected_choice_id: int,
        callback_token: str,
    ) -> VocabSubmitAnswerResult:
        if container.db is None:
            raise RuntimeError("db_not_initialized")

        conn = container.db
        repo = VocabRepository(conn)
        fsm_repo = FsmRuntimeRepository(conn)

        user_id = await repo.upsert_user_from_telegram(tg_user)
        active = await repo.get_active_vocab_attempt(user_id=user_id)
        if active is None:
            raise RuntimeError("active_vocab_attempt_not_found")

        state = await fsm_repo.get_state(ModeCode.VOCAB, user_id)
        if state is None:
            raise RuntimeError("fsm_state_not_found_for_active_attempt")

        if state.status != AttemptStatus.AWAITING_ANSWER:
            raise RuntimeError(f"answer_not_expected:{state.status.value}")

        if state.expected_callback_token != callback_token:
            raise RuntimeError("stale_callback_token")

        selected = await repo.get_choice_with_item(choice_id=selected_choice_id)
        if selected is None:
            raise RuntimeError("selected_choice_not_found")

        if int(selected["item_id"]) != int(state.current_item_id or "0"):
            raise RuntimeError("choice_item_mismatch")

        processing_state = await fsm_repo.transition(
            mode=ModeCode.VOCAB,
            user_id=user_id,
            expected_revision=state.revision,
            target_status=AttemptStatus.PROCESSING_ANSWER,
            current_item_id=str(int(selected["item_id"])),
            expected_callback_token=None,
            expected_message_id=None,
        )

        is_correct = bool(int(selected["is_correct"]))

        await repo.insert_answer(
            attempt_id=int(active["id"]),
            item_id=int(selected["item_id"]),
            selected_choice_id=int(selected["choice_id"]),
            answer_status="answered",
            is_correct=is_correct,
            latency_ms=None,
        )

        await repo.insert_result_snapshot(
            attempt_id=int(active["id"]),
            step_index=processing_state.current_step,
            payload={
                "item_id": int(selected["item_id"]),
                "selected_choice_id": int(selected["choice_id"]),
                "selected_choice_text": str(selected["choice_text"]),
                "is_correct": is_correct,
                "correct_answer": str(selected["correct_answer"]),
            },
        )

        selector_state = await repo.get_selector_payload_state(attempt_id=int(active["id"]))
        selector_state["last_answer"] = {
            "item_id": int(selected["item_id"]),
            "selected_choice_id": int(selected["choice_id"]),
            "selected_choice_text": str(selected["choice_text"]),
            "is_correct": is_correct,
            "correct_answer": str(selected["correct_answer"]),
        }
        selector_state.pop("current_question", None)
        selector_state.pop("callback_token", None)
        await repo.update_selector_state(
            attempt_id=int(active["id"]),
            payload=selector_state,
        )

        await repo.append_attempt_event(
            attempt_id=int(active["id"]),
            user_id=user_id,
            event_type="answer_submitted",
            step_index=processing_state.current_step,
            item_id=int(selected["item_id"]),
            reason_code="correct" if is_correct else "incorrect",
            payload={
                "selected_choice_id": int(selected["choice_id"]),
                "selected_choice_text": str(selected["choice_text"]),
            },
        )

        selecting_state = await fsm_repo.transition(
            mode=ModeCode.VOCAB,
            user_id=user_id,
            expected_revision=processing_state.revision,
            target_status=AttemptStatus.SELECTING,
            current_item_id=None,
            expected_callback_token=None,
            expected_message_id=None,
        )

        return VocabSubmitAnswerResult(
            mode_run_id=int(active["mode_run_id"]),
            vocab_attempt_id=int(active["id"]),
            step_index=selecting_state.current_step,
            item_id=int(selected["item_id"]),
            selected_choice_id=int(selected["choice_id"]),
            is_correct=is_correct,
            selected_choice_text=str(selected["choice_text"]),
            correct_answer_text=str(selected["correct_answer"]),
            next_status=selecting_state.status.value,
            is_finished=False,
            finish_result=None,
        )


    async def submit_dont_know(
        self,
        *,
        tg_user: TgUser,
        callback_token: str,
    ) -> VocabSubmitDontKnowResult:
        if container.db is None:
            raise RuntimeError("db_not_initialized")

        conn = container.db
        repo = VocabRepository(conn)
        fsm_repo = FsmRuntimeRepository(conn)

        user_id = await repo.upsert_user_from_telegram(tg_user)
        active = await repo.get_active_vocab_attempt(user_id=user_id)
        if active is None:
            raise RuntimeError("active_vocab_attempt_not_found")

        state = await fsm_repo.get_state(ModeCode.VOCAB, user_id)
        if state is None:
            raise RuntimeError("fsm_state_not_found_for_active_attempt")

        if state.status != AttemptStatus.AWAITING_ANSWER:
            raise RuntimeError(f"dont_know_not_expected:{state.status.value}")

        if state.expected_callback_token != callback_token:
            raise RuntimeError("stale_callback_token")

        if state.current_item_id is None:
            raise RuntimeError("current_item_missing_for_dont_know")

        item_id = int(state.current_item_id)

        processing_state = await fsm_repo.transition(
            mode=ModeCode.VOCAB,
            user_id=user_id,
            expected_revision=state.revision,
            target_status=AttemptStatus.PROCESSING_ANSWER,
            current_item_id=str(item_id),
            expected_callback_token=None,
            expected_message_id=None,
        )

        await repo.insert_answer(
            attempt_id=int(active["id"]),
            item_id=item_id,
            selected_choice_id=None,
            answer_status="dont_know",
            answer_kind="dont_know",
            is_correct=False,
            latency_ms=None,
        )

        await repo.bump_attempt_after_answer(
            attempt_id=int(active["id"]),
            is_correct=False,
            is_dont_know=True,
        )

        selector_state = await repo.get_selector_payload_state(attempt_id=int(active["id"]))
        selector_state["last_answer"] = {
            "item_id": item_id,
            "selected_choice_id": None,
            "selected_choice_text": None,
            "is_correct": False,
            "correct_answer": None,
            "answer_kind": "dont_know",
        }
        selector_state.pop("current_question", None)
        selector_state.pop("callback_token", None)
        await repo.update_selector_state(
            attempt_id=int(active["id"]),
            payload=selector_state,
        )

        await repo.append_attempt_event(
            attempt_id=int(active["id"]),
            user_id=user_id,
            event_type="dont_know_selected",
            step_index=processing_state.current_step,
            item_id=item_id,
            reason_code="dont_know",
            payload={"callback_token": callback_token},
        )

        selecting_state = await fsm_repo.transition(
            mode=ModeCode.VOCAB,
            user_id=user_id,
            expected_revision=processing_state.revision,
            target_status=AttemptStatus.SELECTING,
            current_item_id=None,
            expected_callback_token=None,
            expected_message_id=None,
        )

        return VocabSubmitDontKnowResult(
            mode_run_id=int(active["mode_run_id"]),
            vocab_attempt_id=int(active["id"]),
            step_index=processing_state.current_step,
            item_id=item_id,
            answer_kind="dont_know",
            next_status=selecting_state.status.value,
            is_finished=False,
            finish_result=None,
        )


    async def submit_report_error(
        self,
        *,
        tg_user: TgUser,
        callback_token: str,
        reason_code: str = "user_reported_item",
    ) -> VocabReportErrorResult:
        if container.db is None:
            raise RuntimeError("db_not_initialized")

        conn = container.db
        repo = VocabRepository(conn)
        fsm_repo = FsmRuntimeRepository(conn)

        user_id = await repo.upsert_user_from_telegram(tg_user)
        active = await repo.get_active_vocab_attempt(user_id=user_id)
        if active is None:
            raise RuntimeError("active_vocab_attempt_not_found")

        state = await fsm_repo.get_state(ModeCode.VOCAB, user_id)
        if state is None:
            raise RuntimeError("fsm_state_not_found_for_active_attempt")

        if state.status != AttemptStatus.AWAITING_ANSWER:
            raise RuntimeError(f"report_error_not_expected:{state.status.value}")

        if state.expected_callback_token != callback_token:
            raise RuntimeError("stale_callback_token")

        if state.current_item_id is None:
            raise RuntimeError("current_item_missing_for_report_error")

        item_id = int(state.current_item_id)

        processing_state = await fsm_repo.transition(
            mode=ModeCode.VOCAB,
            user_id=user_id,
            expected_revision=state.revision,
            target_status=AttemptStatus.PROCESSING_ANSWER,
            current_item_id=str(item_id),
            expected_callback_token=None,
            expected_message_id=None,
        )

        selector_state = await repo.get_selector_payload_state(attempt_id=int(active["id"]))
        selector_state["last_report"] = {
            "item_id": item_id,
            "reason_code": reason_code,
            "callback_token": callback_token,
        }
        selector_state.pop("current_question", None)
        selector_state.pop("callback_token", None)
        await repo.update_selector_state(
            attempt_id=int(active["id"]),
            payload=selector_state,
        )

        await repo.append_attempt_event(
            attempt_id=int(active["id"]),
            user_id=user_id,
            event_type="item_reported",
            step_index=processing_state.current_step,
            item_id=item_id,
            reason_code=reason_code,
            payload={
                "callback_token": callback_token,
            },
        )

        selecting_state = await fsm_repo.transition(
            mode=ModeCode.VOCAB,
            user_id=user_id,
            expected_revision=processing_state.revision,
            target_status=AttemptStatus.SELECTING,
            current_item_id=None,
            expected_callback_token=None,
            expected_message_id=None,
        )

        return VocabReportErrorResult(
            mode_run_id=int(active["mode_run_id"]),
            vocab_attempt_id=int(active["id"]),
            step_index=processing_state.current_step,
            item_id=item_id,
            action="report_error",
            next_status=selecting_state.status.value,
            is_finished=False,
            finish_result=None,
        )

    async def finish_attempt(
        self,
        *,
        tg_user: TgUser,
        completion_reason: str = "stop_rule_exhausted_items",
    ) -> VocabFinishResult:
        if container.db is None:
            raise RuntimeError("db_not_initialized")

        conn = container.db
        repo = VocabRepository(conn)
        fsm_repo = FsmRuntimeRepository(conn)

        user_id = await repo.upsert_user_from_telegram(tg_user)
        active = await repo.get_active_vocab_attempt(user_id=user_id)
        if active is None:
            raise RuntimeError("active_vocab_attempt_not_found")

        state = await fsm_repo.get_state(ModeCode.VOCAB, user_id)
        if state is None:
            raise RuntimeError("fsm_state_not_found_for_active_attempt")

        if state.status != AttemptStatus.SELECTING:
            raise RuntimeError(f"finish_not_allowed_from:{state.status.value}")

        attempt_stats = await repo.get_attempt_stats(attempt_id=int(active["id"]))
        if attempt_stats is None:
            raise RuntimeError("attempt_stats_not_found")

        answer_stats = await repo.get_attempt_answer_stats(attempt_id=int(active["id"]))

        question_limit = int(attempt_stats["question_limit"])
        questions_answered = int(answer_stats["total_answers"])

        remaining = await repo.count_remaining_items(attempt_id=int(active["id"]))
        if questions_answered < question_limit and remaining > 0:
            raise RuntimeError("finish_not_allowed_items_remaining")

        finishing_state = await fsm_repo.transition(
            mode=ModeCode.VOCAB,
            user_id=user_id,
            expected_revision=state.revision,
            target_status=AttemptStatus.FINISHING,
            current_item_id=None,
            expected_callback_token=None,
            expected_message_id=None,
        )

        stats = await repo.get_attempt_answer_stats(attempt_id=int(active["id"]))
        total_answers = stats["total_answers"]
        correct_answers = stats["correct_answers"]

        if total_answers <= 0:
            estimated_vocab_band = "unknown"
            estimated_vocab_size = 0
            confidence = 0.0
        scoring_rows = await repo.get_scoring_rows(attempt_id=int(active["id"]))
        scoring_input = build_scoring_input_from_events(
            scoring_rows,
            attempt_id=int(active["id"]),
            total_questions=total_answers,
            correct_answers=correct_answers,
        )
        scoring = score_attempt_v1(scoring_input)

        estimated_vocab_band = str(scoring["estimated_vocab_band"])
        estimated_vocab_size = int(scoring["estimated_vocab_size"] or 0)
        confidence = float(scoring["confidence"])

        await repo.finish_vocab_attempt(
            vocab_attempt_id=int(active["id"]),
            mode_run_id=int(active["mode_run_id"]),
            estimated_vocab_band=estimated_vocab_band,
            estimated_vocab_size=estimated_vocab_size,
            confidence=confidence,
            completion_reason=completion_reason,
        )

        await repo.persist_mode_result_final(
            mode_run_id=int(active["mode_run_id"]),
            user_id=user_id,
            estimated_vocab_band=estimated_vocab_band,
            estimated_vocab_size=estimated_vocab_size,
            confidence=confidence,
            completion_reason=completion_reason,
        )

        await repo.upsert_user_mode_priors(
            user_id=user_id,
            mode_run_id=int(active["mode_run_id"]),
            estimated_vocab_band=estimated_vocab_band,
            confidence=confidence,
            recommended_level_start_band=estimated_vocab_band,
        )

        await repo.insert_result_snapshot(
            attempt_id=int(active["id"]),
            step_index=finishing_state.current_step,
            payload={
                "terminal": True,
                "estimated_vocab_band": estimated_vocab_band,
                "estimated_vocab_size": estimated_vocab_size,
                "confidence": confidence,
                "completion_reason": completion_reason,
                "correct_answers": correct_answers,
                "total_answers": total_answers,
            },
        )

        await repo.append_attempt_event(
            attempt_id=int(active["id"]),
            user_id=user_id,
            event_type="attempt_finished",
            step_index=finishing_state.current_step,
            reason_code=completion_reason,
            payload={
                "estimated_vocab_band": estimated_vocab_band,
                "estimated_vocab_size": estimated_vocab_size,
                "confidence": confidence,
                "correct_answers": correct_answers,
                "total_answers": total_answers,
            },
        )

        finished_state = await fsm_repo.transition(
            mode=ModeCode.VOCAB,
            user_id=user_id,
            expected_revision=finishing_state.revision,
            target_status=AttemptStatus.FINISHED,
            current_item_id=None,
            expected_callback_token=None,
            expected_message_id=None,
        )

        await fsm_repo.delete_state(ModeCode.VOCAB, user_id)

        return VocabFinishResult(
            mode_run_id=int(active["mode_run_id"]),
            vocab_attempt_id=int(active["id"]),
            status=finished_state.status.value,
            completion_reason=completion_reason,
            estimated_vocab_band=estimated_vocab_band,
            estimated_vocab_size=estimated_vocab_size,
            confidence=confidence,
            correct_answers=correct_answers,
            total_answers=total_answers,
        )

    async def abort_attempt(
        self,
        *,
        tg_user: TgUser,
        completion_reason: str = "user_aborted",
    ) -> VocabAbortResult:
        if container.db is None:
            raise RuntimeError("db_not_initialized")

        conn = container.db
        repo = VocabRepository(conn)
        fsm_repo = FsmRuntimeRepository(conn)

        user_id = await repo.upsert_user_from_telegram(tg_user)
        active = await repo.get_active_vocab_attempt(user_id=user_id)
        if active is None:
            raise RuntimeError("active_vocab_attempt_not_found")

        state = await fsm_repo.get_state(ModeCode.VOCAB, user_id)
        if state is None:
            raise RuntimeError("fsm_state_not_found_for_active_attempt")

        if state.status in {AttemptStatus.FINISHED, AttemptStatus.ABORTED}:
            raise RuntimeError("attempt_already_terminal")

        terminal_state = await fsm_repo.upsert_terminal_state(
            mode=ModeCode.VOCAB,
            user_id=user_id,
            target_status=AttemptStatus.ABORTED,
        )

        await repo.abort_vocab_attempt(
            vocab_attempt_id=int(active["id"]),
            mode_run_id=int(active["mode_run_id"]),
            completion_reason=completion_reason,
        )

        await repo.append_attempt_event(
            attempt_id=int(active["id"]),
            user_id=user_id,
            event_type="attempt_aborted",
            step_index=terminal_state.current_step,
            reason_code=completion_reason,
            payload={"mode_run_id": int(active["mode_run_id"])},
        )

        await repo.persist_mode_result_stub(
            mode_run_id=int(active["mode_run_id"]),
            user_id=user_id,
            completion_reason=completion_reason,
        )

        await fsm_repo.delete_state(ModeCode.VOCAB, user_id)

        return VocabAbortResult(
            mode_run_id=int(active["mode_run_id"]),
            vocab_attempt_id=int(active["id"]),
            status="aborted",
            completion_reason=completion_reason,
        )
