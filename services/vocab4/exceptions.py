from __future__ import annotations


class InsufficientBankError(Exception):
    """Raised when the certified pool cannot satisfy the next selection step."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason
