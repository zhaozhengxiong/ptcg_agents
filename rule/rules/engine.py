"""Execution engine for IR rules."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .effects import EffectRegistry, registry
from .errors import IRValidationError, OncePerTurnViolation
from .schema import (
    AtomicEffect,
    CardRule,
    Condition,
    EffectNode,
    GateEffect,
    Modifier,
    SequenceEffect,
    TriggerType,
)


@dataclass
class RuntimeState:
    """Keeps track of runtime-scoped metadata used by modifiers."""

    once_per_turn_usage: Dict[str, str] = field(default_factory=dict)

    def claim_once_per_turn(self, modifier_id: str, turn_identifier: str) -> None:
        last_turn = self.once_per_turn_usage.get(modifier_id)
        if last_turn == turn_identifier:
            raise OncePerTurnViolation(modifier_id)
        self.once_per_turn_usage[modifier_id] = turn_identifier


@dataclass
class EffectContext:
    """Runtime context passed to effect handlers."""

    controller: str
    state: Dict[str, Any]
    turn_identifier: str
    source_rule: Optional[str] = None
    variables: Dict[str, Any] = field(default_factory=dict)
    runtime: RuntimeState = field(default_factory=RuntimeState)

    def derive(self, **variables: Any) -> "EffectContext":
        """Return a new context with extended temporary variables."""

        combined = dict(self.variables)
        combined.update(variables)
        return EffectContext(
            controller=self.controller,
            state=self.state,
            turn_identifier=self.turn_identifier,
            source_rule=self.source_rule,
            variables=combined,
            runtime=self.runtime,
        )


class RuleEngine:
    """Applies :class:`CardRule` objects to a given :class:`EffectContext`."""

    def __init__(self, effect_registry: Optional[EffectRegistry] = None) -> None:
        self._registry = effect_registry or registry

    def execute(self, rule: CardRule, context: EffectContext) -> bool:
        """Execute a rule if its trigger conditions are satisfied."""

        if not self._can_trigger(rule, context):
            return False
        self._apply_modifiers(rule.modifiers, context)
        self._execute_node(rule.effect, context)
        return True

    # ------------------------------------------------------------------ helpers
    def _can_trigger(self, rule: CardRule, context: EffectContext) -> bool:
        trigger = rule.trigger
        if trigger.type != TriggerType.MANUAL:
            event = context.variables.get("event")
            if event != trigger.type.value:
                return False
        if trigger.condition is None:
            return True
        return self._evaluate_condition(trigger.condition, context)

    def _apply_modifiers(self, modifiers: list[Modifier], context: EffectContext) -> None:
        for modifier in modifiers:
            if modifier.type == "once_per_turn":
                context.runtime.claim_once_per_turn(modifier.identifier, context.turn_identifier)
            else:  # pragma: no cover - defensive branch for future extensions
                raise IRValidationError(f"Unsupported modifier type '{modifier.type}'")

    def _execute_node(self, node: EffectNode, context: EffectContext) -> None:
        if isinstance(node, AtomicEffect):
            self._registry.apply(node.effect, context, node.parameters)
        elif isinstance(node, SequenceEffect):
            for step in node.steps:
                self._execute_node(step, context)
        elif isinstance(node, GateEffect):
            condition_met = self._evaluate_condition(node.condition, context)
            if condition_met:
                self._execute_node(node.if_true, context)
            elif node.if_false is not None:
                self._execute_node(node.if_false, context)
        else:  # pragma: no cover - exhaustive guard
            raise IRValidationError(f"Unsupported effect node: {type(node)!r}")

    def _evaluate_condition(self, condition: Condition, context: EffectContext) -> bool:
        value = self._resolve_path(condition.path, context)
        if condition.kind == "exists":
            return value is not None
        if condition.kind == "equals":
            return value == condition.value
        raise IRValidationError(f"Unsupported condition kind '{condition.kind}'")

    def _resolve_path(self, path: str, context: EffectContext) -> Any:
        parts = path.split(".")
        if not parts:
            raise IRValidationError("Empty condition path")
        head, *rest = parts
        if head == "state":
            value: Any = context.state
        elif head == "variables":
            value = context.variables
        else:
            # Try variables first, then fall back to state.
            value = context.variables.get(head, context.state.get(head))
        for part in rest:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return None
        return value


__all__ = ["EffectContext", "RuleEngine", "RuntimeState"]
