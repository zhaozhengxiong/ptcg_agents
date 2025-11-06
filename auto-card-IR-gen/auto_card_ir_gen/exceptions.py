"""Custom exception hierarchy for the automatic IR compiler pipeline."""

from __future__ import annotations


class RuleCompilationError(RuntimeError):
    """Base exception raised when the compilation pipeline fails."""


class CardFetchError(RuleCompilationError):
    """Raised when the Pokemon TCG API cannot provide card data."""


class TemplateMatchError(RuleCompilationError):
    """Raised when no rule template can interpret the provided card text."""


class ReviewError(RuleCompilationError):
    """Raised when an invalid review or freeze operation is requested."""


__all__ = [
    "RuleCompilationError",
    "CardFetchError",
    "TemplateMatchError",
    "ReviewError",
]
