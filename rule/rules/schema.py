"""Pydantic models describing the JSON IR format for card rules."""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, RootModel, model_validator


class TriggerType(str, Enum):
    """Enumeration of supported trigger categories."""

    MANUAL = "manual"
    ON_PLAY = "on_play"
    ON_ATTACK = "on_attack"
    ON_KNOCK_OUT = "on_knock_out"


class Condition(BaseModel):
    """A boolean predicate used for triggers and gate effects."""

    model_config = ConfigDict(extra="forbid")
    kind: Literal["equals", "exists"]
    path: str = Field(..., min_length=1, description="Dot separated lookup path")
    value: Optional[Any] = Field(
        default=None,
        description="Target value when ``kind`` is ``equals``. Ignored for ``exists``.",
    )

    @model_validator(mode="after")
    def _validate_value(self) -> "Condition":
        if self.kind == "equals" and self.value is None:
            raise ValueError("equals condition requires a 'value' field")
        return self


class Trigger(BaseModel):
    """Definition of the event that activates a rule."""

    model_config = ConfigDict(extra="forbid")
    type: TriggerType
    condition: Optional[Condition] = None


class AtomicEffect(BaseModel):
    """Leaf node describing an atomic effect handler invocation."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    kind: Literal["atomic"] = Field(alias="type", default="atomic")
    effect: str = Field(..., min_length=1)
    parameters: Dict[str, Any] = Field(default_factory=dict)


class SequenceEffect(BaseModel):
    """Execute a list of effect nodes sequentially."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    kind: Literal["sequence"] = Field(alias="type", default="sequence")
    steps: List["EffectNode"] = Field(default_factory=list, min_length=1)


class GateEffect(BaseModel):
    """Conditionally execute nested effects."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    kind: Literal["gate"] = Field(alias="type", default="gate")
    condition: Condition
    if_true: "EffectNode"
    if_false: Optional["EffectNode"] = None


EffectNode = Annotated[
    Union[AtomicEffect, SequenceEffect, GateEffect],
    Field(discriminator="kind"),
]


class Modifier(BaseModel):
    """Additional behaviour modifiers applied to the top-level effect."""

    model_config = ConfigDict(extra="forbid")
    type: Literal["once_per_turn"]
    identifier: str = Field(..., min_length=1)


class CardRule(BaseModel):
    """Top-level rule definition for a single card ability."""

    model_config = ConfigDict(extra="forbid")
    rule_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    version: str = Field(..., min_length=1)
    trigger: Trigger
    effect: EffectNode
    modifiers: List[Modifier] = Field(default_factory=list)


class CardRuleCollection(RootModel[List[CardRule]]):
    """Helper root model to validate arrays of rules."""


def get_ir_json_schema() -> Dict[str, Any]:
    """Return the JSON schema used to validate card rule payloads."""

    return CardRule.model_json_schema()


__all__ = [
    "AtomicEffect",
    "CardRule",
    "CardRuleCollection",
    "Condition",
    "EffectNode",
    "GateEffect",
    "Modifier",
    "SequenceEffect",
    "Trigger",
    "TriggerType",
    "get_ir_json_schema",
]
