import pytest
from pydantic import ValidationError

pytestmark = pytest.mark.filterwarnings("ignore::pydantic.json_schema.PydanticJsonSchemaWarning")

from rules.schema import (
    AtomicEffect,
    CardRule,
    Condition,
    SequenceEffect,
    Trigger,
    TriggerType,
    get_ir_json_schema,
)


def test_card_rule_validates_and_exposes_schema() -> None:
    rule = CardRule(
        rule_id="test.draw",
        name="Test Draw",
        version="1.0",
        trigger=Trigger(type=TriggerType.MANUAL),
        effect=AtomicEffect(effect="Draw", parameters={"count": 2}),
    )
    schema = get_ir_json_schema()
    assert "properties" in schema
    assert rule.effect.effect == "Draw"


def test_condition_requires_value_for_equals() -> None:
    with pytest.raises(ValidationError):
        Condition(kind="equals", path="state.flags.ready")


def test_sequence_requires_steps() -> None:
    with pytest.raises(ValidationError):
        SequenceEffect(steps=[])
