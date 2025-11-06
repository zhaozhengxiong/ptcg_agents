"""Public package interface for the rules/IR subsystem."""

from .engine import EffectContext, RuleEngine
from .errors import (
    EffectExecutionError,
    IRValidationError,
    OncePerTurnViolation,
    RuleNotFoundError,
    RuleVersionMismatchError,
)
from .loader import RuleRepository
from .schema import (
    AtomicEffect,
    CardRule,
    Condition,
    EffectNode,
    GateEffect,
    Modifier,
    SequenceEffect,
    Trigger,
    TriggerType,
    get_ir_json_schema,
)

__all__ = [
    "AtomicEffect",
    "CardRule",
    "Condition",
    "EffectContext",
    "EffectExecutionError",
    "EffectNode",
    "GateEffect",
    "IRValidationError",
    "Modifier",
    "OncePerTurnViolation",
    "RuleEngine",
    "RuleNotFoundError",
    "RuleRepository",
    "RuleVersionMismatchError",
    "SequenceEffect",
    "Trigger",
    "TriggerType",
    "get_ir_json_schema",
]
