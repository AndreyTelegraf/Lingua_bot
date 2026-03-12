from __future__ import annotations

from dataclasses import asdict

import aiosqlite

from domain.attempts.fsm import RuntimeState, require_transition
from domain.shared.enums import AttemptStatus, ModeCode


class FsmRuntimeRepository:
    def __init__(self, conn: aiosqlite.Connection) -> None:
        self.conn = conn

    async def get_state(self, mode: ModeCode, user_id: int) -> RuntimeState | None:
        cursor = await self.conn.execute(
            """
            SELECT mode, user_id, run_id, status, current_step, current_item_id,
                   expected_callback_token, expected_message_id, revision
            FROM fsm_runtime_state
            WHERE mode = ? AND user_id = ?
            """,
            (mode.value, user_id),
        )
        row = await cursor.fetchone()
        if row is None:
            return None

        return RuntimeState(
            mode=ModeCode(str(row["mode"])),
            user_id=int(row["user_id"]),
            run_id=int(row["run_id"]),
            status=AttemptStatus(str(row["status"])),
            current_step=int(row["current_step"]),
            current_item_id=row["current_item_id"],
            expected_callback_token=row["expected_callback_token"],
            expected_message_id=row["expected_message_id"],
            revision=int(row["revision"]),
        )

    async def create_state(
        self,
        *,
        mode: ModeCode,
        user_id: int,
        run_id: int,
        status: AttemptStatus = AttemptStatus.IDLE,
    ) -> RuntimeState:
        await self.conn.execute(
            """
            INSERT INTO fsm_runtime_state (
                mode, user_id, run_id, status, current_step, revision
            )
            VALUES (?, ?, ?, ?, 0, 0)
            """,
            (mode.value, user_id, run_id, status.value),
        )
        await self.conn.commit()

        state = await self.get_state(mode, user_id)
        if state is None:
            raise RuntimeError("fsm_state_not_created")
        return state

    async def transition(
        self,
        *,
        mode: ModeCode,
        user_id: int,
        expected_revision: int,
        target_status: AttemptStatus,
        current_item_id: str | None = None,
        expected_callback_token: str | None = None,
        expected_message_id: int | None = None,
        increment_step: bool = False,
    ) -> RuntimeState:
        state = await self.get_state(mode, user_id)
        if state is None:
            raise RuntimeError("fsm_state_not_found")

        require_transition(state.status, target_status)

        new_step = state.current_step + 1 if increment_step else state.current_step

        cursor = await self.conn.execute(
            """
            UPDATE fsm_runtime_state
            SET status = ?,
                current_step = ?,
                current_item_id = ?,
                expected_callback_token = ?,
                expected_message_id = ?,
                revision = revision + 1,
                last_transition_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE mode = ?
              AND user_id = ?
              AND revision = ?
            """,
            (
                target_status.value,
                new_step,
                current_item_id,
                expected_callback_token,
                expected_message_id,
                mode.value,
                user_id,
                expected_revision,
            ),
        )
        await self.conn.commit()

        if cursor.rowcount != 1:
            raise RuntimeError("fsm_revision_conflict")

        new_state = await self.get_state(mode, user_id)
        if new_state is None:
            raise RuntimeError("fsm_state_missing_after_transition")
        return new_state

    async def delete_state(self, mode: ModeCode, user_id: int) -> None:
        await self.conn.execute(
            "DELETE FROM fsm_runtime_state WHERE mode = ? AND user_id = ?",
            (mode.value, user_id),
        )
        await self.conn.commit()

    async def upsert_terminal_state(
        self,
        *,
        mode: ModeCode,
        user_id: int,
        target_status: AttemptStatus,
    ) -> RuntimeState:
        if target_status not in {AttemptStatus.FINISHED, AttemptStatus.ABORTED}:
            raise ValueError("terminal_status_required")

        state = await self.get_state(mode, user_id)
        if state is None:
            raise RuntimeError("fsm_state_not_found")

        cursor = await self.conn.execute(
            """
            UPDATE fsm_runtime_state
            SET status = ?,
                revision = revision + 1,
                last_transition_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE mode = ?
              AND user_id = ?
            """,
            (target_status.value, mode.value, user_id),
        )
        await self.conn.commit()

        if cursor.rowcount != 1:
            raise RuntimeError("fsm_terminal_update_failed")

        new_state = await self.get_state(mode, user_id)
        if new_state is None:
            raise RuntimeError("fsm_state_missing_after_terminal")
        return new_state


def runtime_state_to_dict(state: RuntimeState) -> dict[str, object]:
    return asdict(state)
