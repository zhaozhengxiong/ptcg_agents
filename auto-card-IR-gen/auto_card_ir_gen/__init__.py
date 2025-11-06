"""Automatic Pokemon TCG card rule compilation utilities."""

from __future__ import annotations

from .clients import PokemonTCGClient
from .exceptions import CardFetchError, ReviewError, RuleCompilationError, TemplateMatchError
from .pipeline import CompiledRule, CompilationResult, RuleCompilationPipeline
from .storage import CardRuleRecord, CardSourceRecord, Storage
from .templates import RuleTemplateEngine

__all__ = [
    "PokemonTCGClient",
    "CardFetchError",
    "ReviewError",
    "RuleCompilationError",
    "TemplateMatchError",
    "CompiledRule",
    "CompilationResult",
    "RuleCompilationPipeline",
    "CardRuleRecord",
    "CardSourceRecord",
    "Storage",
    "RuleTemplateEngine",
]
