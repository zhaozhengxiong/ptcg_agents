"""Custom exception types used across the project."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ErrorDetails:
    """Structured metadata associated with an exception."""

    code: str
    message: str


class GameRuleViolation(Exception):
    """Base class for rule related exceptions."""

    error_code = "ERR_RULE_VIOLATION"

    def __init__(self, message: str, *, details: ErrorDetails | None = None) -> None:
        super().__init__(message)
        self.details = details or ErrorDetails(code=self.error_code, message=message)

    @property
    def code(self) -> str:
        return self.details.code


class IllegalActionError(GameRuleViolation):
    """Raised when an agent attempts to execute an illegal action."""

    error_code = "ERR_ILLEGAL_ACTION"

    def __init__(self, message: str) -> None:
        super().__init__(message, details=ErrorDetails(code=self.error_code, message=message))


__all__ = ["ErrorDetails", "GameRuleViolation", "IllegalActionError"]
