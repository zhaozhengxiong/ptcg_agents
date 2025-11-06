import pytest

from rules.engine import EffectContext, RuleEngine
from rules.errors import OncePerTurnViolation
from rules.schema import (
    AtomicEffect,
    CardRule,
    Condition,
    GateEffect,
    Modifier,
    SequenceEffect,
    Trigger,
    TriggerType,
)


def make_context() -> EffectContext:
    state = {
        "players": {
            "p1": {"deck": ["C1", "C2", "C3"], "hand": []},
            "p2": {"deck": [], "hand": []},
        }
    }
    return EffectContext(controller="p1", state=state, turn_identifier="turn-1")


def test_sequence_execution_and_damage_application() -> None:
    engine = RuleEngine()
    rule = CardRule(
        rule_id="seq.rule",
        name="Sequence",
        version="1.0",
        trigger=Trigger(type=TriggerType.MANUAL),
        effect=SequenceEffect(
            steps=[
                AtomicEffect(effect="Draw", parameters={"count": 2}),
                AtomicEffect(effect="AddDamage", parameters={"target": "p2_active", "amount": 30}),
            ]
        ),
    )
    context = make_context()
    executed = engine.execute(rule, context)
    assert executed is True
    assert context.state["players"]["p1"]["hand"] == ["C1", "C2"]
    assert context.state["damage"]["p2_active"] == 30


def test_gate_effect_uses_variables_for_condition() -> None:
    engine = RuleEngine()
    gate_rule = CardRule(
        rule_id="gate.rule",
        name="Gate",
        version="1.0",
        trigger=Trigger(type=TriggerType.MANUAL),
        effect=GateEffect(
            condition=Condition(kind="equals", path="variables.flags.has_target", value=True),
            if_true=AtomicEffect(effect="AddDamage", parameters={"target": "p2_active", "amount": 10}),
            if_false=AtomicEffect(effect="AddDamage", parameters={"target": "p2_active", "amount": 1}),
        ),
    )
    context = make_context()
    context.variables = {"flags": {"has_target": True}}
    engine.execute(gate_rule, context)
    assert context.state["damage"]["p2_active"] == 10
    context_false = context.derive(flags={"has_target": False})
    engine.execute(gate_rule, context_false)
    assert context.state["damage"]["p2_active"] == 11


def test_once_per_turn_modifier_blocks_second_execution() -> None:
    engine = RuleEngine()
    rule = CardRule(
        rule_id="once.rule",
        name="Once",
        version="1.0",
        trigger=Trigger(type=TriggerType.MANUAL),
        effect=AtomicEffect(effect="Draw", parameters={"count": 1}),
        modifiers=[Modifier(type="once_per_turn", identifier="once.draw")],
    )
    context = make_context()
    engine.execute(rule, context)
    with pytest.raises(OncePerTurnViolation):
        engine.execute(rule, context)


def test_trigger_requires_matching_event() -> None:
    engine = RuleEngine()
    rule = CardRule(
        rule_id="event.rule",
        name="Event",
        version="1.0",
        trigger=Trigger(type=TriggerType.ON_PLAY),
        effect=AtomicEffect(effect="Draw", parameters={"count": 1}),
    )
    context = make_context()
    assert engine.execute(rule, context) is False
    played_context = context.derive(event="on_play")
    assert engine.execute(rule, played_context) is True
