"""Core data structures for cards, decks and zones.

This module provides the foundational abstractions for manipulating card
instances inside the battle environment.  It covers three closely related
concerns:

* :class:`Card` – immutable card records with globally unique identifiers.
* :class:`Zone` – containers that host cards (deck, hand, discard pile …).
* :class:`Deck` – a specialised zone with draw and shuffle helpers.

In addition to the data structures, convenience loaders are provided for
importing deck lists from JSON definitions as well as the "Copy to Clipboard"
format exported by https://limitlesstcg.com/.  Both helpers rely on the same
underlying card creation pipeline to guarantee consistent identifiers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import itertools
import json
import random
import re
from typing import Dict, Iterable, Iterator, List, Optional


class CardSuperType(Enum):
    """Supported top-level card supertypes."""

    POKEMON = "Pokemon"
    TRAINER = "Trainer"
    ENERGY = "Energy"

    @classmethod
    def from_string(cls, value: str) -> "CardSuperType":
        """Normalise a string value into a :class:`CardSuperType`.

        ``Limitless`` deck exports use ``Pokemon`` whereas other sources may use
        ``Pokémon``.  The method accepts multiple spellings and raises a
        ``ValueError`` for unsupported values so that upstream code can surface
        meaningful error messages to the user.
        """

        normalised = value.strip().lower()
        if normalised in {"pokemon", "pokémon"}:
            return cls.POKEMON
        if normalised == "trainer":
            return cls.TRAINER
        if normalised == "energy":
            return cls.ENERGY
        raise ValueError(f"Unsupported card supertype: {value!r}")


_CARD_UID_COUNTER = itertools.count(start=1)


def reset_card_uid_counter() -> None:
    """Reset the card UID counter.

    The helper is intended for deterministic unit tests only.  Game code should
    never reset the counter during real matches because that would break the
    uniqueness guarantee.
    """

    global _CARD_UID_COUNTER
    _CARD_UID_COUNTER = itertools.count(start=1)


@dataclass(frozen=True)
class Card:
    """Immutable representation of a physical card copy."""

    name: str
    supertype: CardSuperType
    set_code: str
    number: str
    metadata: Dict[str, str] = field(default_factory=dict, compare=False)
    card_uid: int = field(init=False)

    def __post_init__(self) -> None:  # pragma: no cover - trivial attribute set
        uid = next(_CARD_UID_COUNTER)
        object.__setattr__(self, "card_uid", uid)


class ZoneType(Enum):
    """Enumeration of the supported battle zones."""

    DECK = "deck"
    HAND = "hand"
    DISCARD = "discard"
    PRIZE = "prize"
    BENCH = "bench"
    ACTIVE = "active"


class CardTracker:
    """Tracks the last known zone for every card UID."""

    def __init__(self) -> None:
        self._locations: Dict[int, ZoneType] = {}

    def update(self, card: Card, zone_type: ZoneType) -> None:
        self._locations[card.card_uid] = zone_type

    def bulk_update(self, cards: Iterable[Card], zone_type: ZoneType) -> None:
        for card in cards:
            self.update(card, zone_type)

    def remove(self, card_uid: int) -> None:
        self._locations.pop(card_uid, None)

    def location_of(self, card_uid: int) -> Optional[ZoneType]:
        return self._locations.get(card_uid)


class Zone:
    """Generic container for cards belonging to a specific zone."""

    def __init__(
        self,
        zone_type: ZoneType,
        cards: Optional[Iterable[Card]] = None,
        *,
        tracker: Optional[CardTracker] = None,
    ) -> None:
        self.zone_type = zone_type
        self._cards: List[Card] = list(cards or [])
        self._tracker = tracker
        if tracker is not None:
            tracker.bulk_update(self._cards, self.zone_type)

    def __len__(self) -> int:
        return len(self._cards)

    def __iter__(self) -> Iterator[Card]:
        return iter(self._cards)

    def cards(self) -> List[Card]:
        """Return a copy of the current card list."""

        return list(self._cards)

    @property
    def tracker(self) -> Optional[CardTracker]:
        return self._tracker

    def add_card(self, card: Card, position: str = "top") -> None:
        """Add a card to the zone at the requested position."""

        if position not in {"top", "bottom"}:
            raise ValueError("position must be 'top' or 'bottom'")
        if position == "top":
            self._cards.insert(0, card)
        else:
            self._cards.append(card)
        if self._tracker is not None:
            self._tracker.update(card, self.zone_type)

    def add_cards(self, cards: Iterable[Card], position: str = "bottom") -> None:
        """Bulk add cards to the zone."""

        for card in cards:
            self.add_card(card, position=position)

    def remove_card(self, card_uid: int) -> Card:
        """Remove and return a card by ``card_uid``."""

        for idx, card in enumerate(self._cards):
            if card.card_uid == card_uid:
                removed = self._cards.pop(idx)
                if self._tracker is not None:
                    self._tracker.remove(card_uid)
                return removed
        raise KeyError(f"Card UID {card_uid} not found in {self.zone_type.value}")

    def pop_top(self) -> Card:
        """Remove and return the top card."""

        if not self._cards:
            raise IndexError(f"{self.zone_type.value} is empty")
        card = self._cards.pop(0)
        if self._tracker is not None:
            self._tracker.remove(card.card_uid)
        return card

    def move_card_to(self, card_uid: int, other: "Zone", position: str = "top") -> Card:
        """Move a card to another zone and return it."""

        card = self.remove_card(card_uid)
        other.add_card(card, position=position)
        return card


class Deck(Zone):
    """Representation of a player's deck."""

    def __init__(
        self,
        name: str,
        cards: Iterable[Card],
        *,
        tracker: Optional[CardTracker] = None,
    ) -> None:
        if tracker is None:
            tracker = CardTracker()
        super().__init__(ZoneType.DECK, cards, tracker=tracker)
        self.name = name

    def shuffle(self, seed: Optional[int] = None) -> None:
        """Shuffle the deck in place.

        When a seed is supplied the shuffle becomes deterministic which is
        extremely useful for deterministic tests and reproducible simulations.
        """

        rng = random.Random(seed)
        rng.shuffle(self._cards)

    def draw(self, count: int = 1) -> List[Card]:
        if count < 0:
            raise ValueError("count must be non-negative")
        drawn: List[Card] = []
        for _ in range(min(count, len(self._cards))):
            drawn.append(self.pop_top())
        return drawn


def _build_cards(
    *,
    name: str,
    supertype: CardSuperType,
    set_code: str,
    number: str,
    count: int,
    metadata: Optional[Dict[str, str]] = None,
) -> List[Card]:
    metadata = metadata or {}
    return [
        Card(name=name, supertype=supertype, set_code=set_code, number=number, metadata=metadata)
        for _ in range(count)
    ]


def load_deck_from_json(data: Dict) -> Deck:
    """Create a :class:`Deck` from a JSON-like dictionary."""

    try:
        name = data["name"]
        raw_cards = data["cards"]
    except KeyError as exc:  # pragma: no cover - defensive guard
        raise ValueError("Deck JSON must contain 'name' and 'cards'") from exc

    tracker = CardTracker()
    cards: List[Card] = []
    for entry in raw_cards:
        try:
            count = int(entry["count"])
            card_name = entry["name"]
            supertype = CardSuperType.from_string(entry["supertype"])
            set_code = entry["set_code"]
            number = str(entry["number"])
        except KeyError as exc:
            raise ValueError(f"Invalid card entry: missing field {exc.args[0]!r}") from exc
        metadata = {
            key: value
            for key, value in entry.items()
            if key not in {"count", "name", "supertype", "set_code", "number"}
        }
        cards.extend(
            _build_cards(
                name=card_name,
                supertype=supertype,
                set_code=set_code,
                number=number,
                count=count,
                metadata=metadata,
            )
        )
    return Deck(name=name, cards=cards, tracker=tracker)


_LIMITLESS_SECTION_RE = re.compile(r"^(?P<section>[A-Za-zéÉ]+):\s*(?P<count>\d+)")


def load_deck_from_limitless(text: str, *, name: str = "Limitless Deck") -> Deck:
    """Parse the ``Copy to Clipboard`` format from LimitlessTCG."""

    tracker = CardTracker()
    cards: List[Card] = []
    current_supertype: Optional[CardSuperType] = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        section_match = _LIMITLESS_SECTION_RE.match(line)
        if section_match:
            section_name = section_match.group("section")
            current_supertype = CardSuperType.from_string(section_name)
            continue

        if current_supertype is None:
            raise ValueError("Card line encountered before section header")

        parts = line.split()
        if len(parts) < 4:
            raise ValueError(f"Unrecognised Limitless card line: {line!r}")
        count = int(parts[0])
        set_code = parts[-2]
        number = parts[-1]
        name_tokens = parts[1:-2]
        card_name = " ".join(name_tokens)
        cards.extend(
            _build_cards(
                name=card_name,
                supertype=current_supertype,
                set_code=set_code,
                number=number,
                count=count,
            )
        )

    return Deck(name=name, cards=cards, tracker=tracker)


def load_deck_from_json_file(path: str) -> Deck:
    """Convenience wrapper to load a deck from a JSON file on disk."""

    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    return load_deck_from_json(data)

