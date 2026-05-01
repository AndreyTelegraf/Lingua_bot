from __future__ import annotations


class InsufficientBankError(Exception):
    """Raised when the certified pool cannot satisfy the next selection step."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class AttemptStateError(Exception):
    """Raised when a status-guarded write finds the attempt in the wrong state."""

    def __init__(self, attempt_id: int, reason: str) -> None:
        super().__init__(reason)
        self.attempt_id = attempt_id
        self.reason = reason
