"""Custom exceptions raised by the rules/IR subsystem."""

from __future__ import annotations


class IRValidationError(ValueError):
    """Raised when IR payloads fail schema validation."""


class EffectExecutionError(RuntimeError):
    """Raised when an error occurs while executing an IR effect."""


class OncePerTurnViolation(EffectExecutionError):
    """Raised when a once-per-turn modifier is triggered more than once."""

    def __init__(self, modifier_id: str) -> None:
        super().__init__(f"Once-per-turn limit reached for modifier '{modifier_id}'")
        self.modifier_id = modifier_id


class RuleNotFoundError(KeyError):
    """Raised when a requested rule identifier cannot be resolved."""

    def __init__(self, rule_id: str) -> None:
        super().__init__(f"Rule '{rule_id}' not found")
        self.rule_id = rule_id


class RuleVersionMismatchError(IRValidationError):
    """Raised when the requested rule version does not match the stored one."""

    def __init__(self, rule_id: str, expected: str, actual: str) -> None:
        super().__init__(
            f"Rule '{rule_id}' version mismatch: expected {expected}, found {actual}"
        )
        self.rule_id = rule_id
        self.expected = expected
        self.actual = actual


__all__ = [
    "EffectExecutionError",
    "IRValidationError",
    "OncePerTurnViolation",
    "RuleNotFoundError",
    "RuleVersionMismatchError",
]
