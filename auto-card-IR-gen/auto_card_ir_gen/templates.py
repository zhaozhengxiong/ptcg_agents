"""Rule template helpers converting card text into IR structures."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Iterable, List, Mapping, MutableMapping, Optional

from rules.schema import (
    AtomicEffect,
    CardRule,
    Condition,
    EffectNode,
    GateEffect,
    Modifier,
    SequenceEffect,
    Trigger,
    TriggerType,
)

from .exceptions import TemplateMatchError


@dataclass(slots=True)
class TemplateMatch:
    """Container with the result of applying a rule template."""

    rule: CardRule
    description: str


class RuleTemplate:
    """A template is simply a callable generating a :class:`CardRule`."""

    def __init__(self, matcher: Callable[[str], Optional[EffectNode]], *, description: str) -> None:
        self._matcher = matcher
        self._description = description

    def try_build(
        self,
        *,
        card: Mapping[str, object],
        ability: Mapping[str, object],
        version: str,
    ) -> Optional[TemplateMatch]:
        text = str(ability.get("text", ""))
        match = self._matcher(text)
        if match is None:
            return None
        rule_id = _build_rule_id(card, ability)
        rule = CardRule(
            rule_id=rule_id,
            name=str(ability.get("name", card.get("name", "Ability"))),
            version=version,
            trigger=_infer_trigger(text),
            effect=match,
            modifiers=list(_collect_modifiers(text, rule_id)),
        )
        return TemplateMatch(rule=rule, description=self._description)


def _build_rule_id(card: Mapping[str, object], ability: Mapping[str, object]) -> str:
    card_id = str(card.get("id", "card"))
    ability_name = str(ability.get("name", "ability"))
    slug = re.sub(r"[^a-z0-9]+", "-", ability_name.lower()).strip("-") or "ability"
    return f"{card_id}.{slug}"


def _infer_trigger(text: str) -> Trigger:
    lowered = text.lower()
    if "when you play this pokémon" in lowered or "when you play this pokemon" in lowered:
        return Trigger(type=TriggerType.ON_PLAY)
    if "when this pokémon attacks" in lowered or "when this pokemon attacks" in lowered:
        return Trigger(type=TriggerType.ON_ATTACK)
    return Trigger(type=TriggerType.MANUAL)


def _collect_modifiers(text: str, rule_id: str) -> Iterable[Modifier]:
    lowered = text.lower()
    if "once during your turn" in lowered:
        yield Modifier(type="once_per_turn", identifier=f"{rule_id}.once")


def _match_draw_effect(text: str) -> Optional[EffectNode]:
    draw_pattern = re.compile(r"draw (?P<count>\d+) cards?", re.IGNORECASE)
    once_pattern = re.compile(r"flip a coin\.\s*if heads, draw (?P<count>\d+) cards?", re.IGNORECASE)
    coin_match = once_pattern.search(text)
    if coin_match:
        count = int(coin_match.group("count"))
        return GateEffect(
            condition=Condition(kind="equals", path="variables.coin_flip", value="heads"),
            if_true=AtomicEffect(effect="Draw", parameters={"count": count}),
            if_false=AtomicEffect(effect="Draw", parameters={"count": 0}),
        )
    match = draw_pattern.search(text)
    if match:
        count = int(match.group("count"))
        return AtomicEffect(effect="Draw", parameters={"count": count})
    return None


def _match_search_effect(text: str) -> Optional[EffectNode]:
    pattern = re.compile(
        r"search your deck for (?:up to )?(?P<count>\d+) (?P<target>[a-z\s]+?) card", re.IGNORECASE
    )
    match = pattern.search(text)
    if not match:
        return None
    count = int(match.group("count"))
    target = match.group("target").strip()
    steps: List[EffectNode] = []
    for _ in range(count):
        steps.append(
            AtomicEffect(
                effect="SearchDeck",
                parameters={"card_name": target, "destination": "hand"},
            )
        )
    return SequenceEffect(steps=steps)


def _match_damage_effect(text: str) -> Optional[EffectNode]:
    pattern = re.compile(r"this attack does (?P<amount>\d+) more damage", re.IGNORECASE)
    match = pattern.search(text)
    if not match:
        return None
    amount = int(match.group("amount"))
    return AtomicEffect(effect="AddDamage", parameters={"amount": amount, "target": "opponent"})


_DEFAULT_TEMPLATES: List[RuleTemplate] = [
    RuleTemplate(_match_draw_effect, description="Draw cards"),
    RuleTemplate(_match_search_effect, description="Search deck"),
    RuleTemplate(_match_damage_effect, description="Increase damage"),
]


class RuleTemplateEngine:
    """Apply simple pattern-based templates to Pokemon card abilities."""

    def __init__(self, templates: Optional[Iterable[RuleTemplate]] = None) -> None:
        self._templates = list(templates or _DEFAULT_TEMPLATES)

    def build_rules(self, card: Mapping[str, object]) -> List[TemplateMatch]:
        abilities = card.get("abilities", [])
        version = _resolve_version(card)
        matches: List[TemplateMatch] = []
        for ability in abilities if isinstance(abilities, list) else []:
            if not isinstance(ability, Mapping):
                continue
            for template in self._templates:
                match = template.try_build(card=card, ability=ability, version=version)
                if match is not None:
                    matches.append(match)
                    break
            else:  # pragma: no cover - only triggered for unsupported abilities
                raise TemplateMatchError(
                    f"No template could parse ability '{ability.get('name', 'Unnamed')}'"
                )
        if not matches:
            raise TemplateMatchError(f"Card '{card.get('id', 'unknown')}' did not match any template")
        return matches


def _resolve_version(card: Mapping[str, object]) -> str:
    set_info = card.get("set", {})
    if isinstance(set_info, Mapping):
        set_id = str(set_info.get("id", "set"))
        release = str(set_info.get("releaseDate", "v1"))
        return f"{set_id}-{release}"
    return "unknown"


__all__ = [
    "RuleTemplateEngine",
    "RuleTemplate",
    "TemplateMatch",
]
