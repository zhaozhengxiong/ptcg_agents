"""Effect handler registry and built-in atomic effect implementations."""

from __future__ import annotations

from typing import Any, Dict, MutableMapping, Optional, Protocol, TypeVar

from .errors import EffectExecutionError

if False:  # pragma: no cover - typing only
    from .engine import EffectContext


class EffectHandler(Protocol):
    """Callable protocol for effect handlers."""

    def __call__(self, context: "EffectContext", parameters: Dict[str, Any]) -> None:  # pragma: no cover - protocol
        ...


HandlerT = TypeVar("HandlerT", bound=EffectHandler)


class EffectRegistry:
    """Registry keeping the mapping between effect identifiers and callables."""

    def __init__(self) -> None:
        self._handlers: Dict[str, EffectHandler] = {}

    def register(self, name: str, handler: Optional[HandlerT] = None):  # type: ignore[override]
        if handler is None:
            def decorator(func: HandlerT) -> HandlerT:
                self.register(name, func)
                return func

            return decorator
        if name in self._handlers:
            raise ValueError(f"Handler already registered for effect '{name}'")
        self._handlers[name] = handler
        return handler

    def get(self, name: str) -> EffectHandler:
        try:
            return self._handlers[name]
        except KeyError as exc:  # pragma: no cover - defensive branch
            raise EffectExecutionError(f"Unknown effect '{name}'") from exc

    def apply(self, name: str, context: "EffectContext", parameters: Dict[str, Any]) -> None:
        handler = self.get(name)
        handler(context, parameters)


def _ensure_zone(mapping: MutableMapping[str, Any], key: str) -> MutableMapping[str, Any]:
    zone = mapping.get(key)
    if zone is None:
        zone = []
        mapping[key] = zone
    if not isinstance(zone, list):
        raise EffectExecutionError(f"Zone '{key}' is not a list-like container")
    return zone  # type: ignore[return-value]


registry = EffectRegistry()


@registry.register("Draw")
def draw_cards(context: "EffectContext", parameters: Dict[str, Any]) -> None:
    """Move cards from the deck to the hand of the affected player."""

    player = parameters.get("player", context.controller)
    count = int(parameters.get("count", 1))
    players = context.state.setdefault("players", {})
    player_state = players.get(player)
    if player_state is None:
        raise EffectExecutionError(f"Player '{player}' not found in context state")
    deck = _ensure_zone(player_state, "deck")
    hand = _ensure_zone(player_state, "hand")
    for _ in range(count):
        if not deck:
            break
        hand.append(deck.pop(0))


@registry.register("SearchDeck")
def search_deck(context: "EffectContext", parameters: Dict[str, Any]) -> None:
    """Search the player's deck for a card and move it to a destination zone."""

    player = parameters.get("player", context.controller)
    card_name = parameters.get("card_name")
    if not card_name:
        raise EffectExecutionError("SearchDeck requires 'card_name'")
    destination = parameters.get("destination", "hand")
    players = context.state.setdefault("players", {})
    player_state = players.get(player)
    if player_state is None:
        raise EffectExecutionError(f"Player '{player}' not found in context state")
    deck = _ensure_zone(player_state, "deck")
    dest_zone = _ensure_zone(player_state, destination)
    for idx, card in enumerate(deck):
        if card == card_name:
            dest_zone.append(deck.pop(idx))
            return
    raise EffectExecutionError(f"Card '{card_name}' not found in deck")


@registry.register("AddDamage")
def add_damage(context: "EffectContext", parameters: Dict[str, Any]) -> None:
    """Increase the damage counter for a given target."""

    target = parameters.get("target")
    amount = int(parameters.get("amount", 0))
    if target is None:
        raise EffectExecutionError("AddDamage requires a 'target'")
    if amount < 0:
        raise EffectExecutionError("AddDamage amount must be non-negative")
    damage_pool = context.state.setdefault("damage", {})
    current = int(damage_pool.get(target, 0))
    damage_pool[target] = current + amount


__all__ = ["EffectRegistry", "registry", "draw_cards", "search_deck", "add_damage"]
