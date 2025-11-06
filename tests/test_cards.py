import pytest

from core import (
    CardSuperType,
    Deck,
    Zone,
    ZoneType,
    load_deck_from_json,
    load_deck_from_limitless,
    reset_card_uid_counter,
)


@pytest.fixture(autouse=True)
def _reset_uid_counter() -> None:
    reset_card_uid_counter()


def test_load_deck_from_json_creates_unique_cards():
    deck_data = {
        "name": "Test Deck",
        "cards": [
            {
                "count": 2,
                "name": "Charmander",
                "supertype": "Pokemon",
                "set_code": "PAF",
                "number": "7",
                "rarity": "Common",
            },
            {
                "count": 1,
                "name": "Professor's Research",
                "supertype": "Trainer",
                "set_code": "BRS",
                "number": 147,
            },
        ],
    }

    deck = load_deck_from_json(deck_data)

    assert isinstance(deck, Deck)
    assert len(deck) == 3
    uids = {card.card_uid for card in deck}
    assert len(uids) == 3


def test_zone_tracks_locations_with_tracker():
    deck_data = {
        "name": "Tracker Deck",
        "cards": [
            {
                "count": 1,
                "name": "Pikachu",
                "supertype": "Pokemon",
                "set_code": "SVI",
                "number": "33",
            },
            {
                "count": 1,
                "name": "Nest Ball",
                "supertype": "Trainer",
                "set_code": "SVI",
                "number": "181",
            },
        ],
    }

    deck = load_deck_from_json(deck_data)
    tracker = deck.tracker
    assert tracker is not None

    top_card = deck.draw(1)[0]
    assert tracker.location_of(top_card.card_uid) is None

    hand = Zone(ZoneType.HAND, tracker=tracker)
    hand.add_card(top_card)
    assert tracker.location_of(top_card.card_uid) == ZoneType.HAND


def test_load_deck_from_limitless_parses_sections():
    limitless_data = """
    Pokémon: 21
    4 Charmander PAF 7
    2 Charmeleon MEW 5

    Trainer: 2
    1 Ultra Ball SVI 196
    1 Rare Candy SVI 191

    Energy: 1
    1 Fire Energy SVE 18
    """

    deck = load_deck_from_limitless(limitless_data, name="Charizard EX")

    assert deck.name == "Charizard EX"
    assert len(deck) == 9

    pokemon = [card for card in deck if card.supertype == CardSuperType.POKEMON]
    assert len(pokemon) == 6


def test_limitless_parser_rejects_invalid_lines():
    with pytest.raises(ValueError):
        load_deck_from_limitless("4 Charmander PAF 7")


def test_deck_shuffle_and_draw_are_deterministic():
    deck_data = {
        "name": "Shuffle Deck",
        "cards": [
            {
                "count": 1,
                "name": f"Card {i}",
                "supertype": "Trainer",
                "set_code": "SET",
                "number": str(i),
            }
            for i in range(3)
        ],
    }

    deck = load_deck_from_json(deck_data)
    deck.shuffle(seed=42)
    drawn = deck.draw(2)

    assert len(drawn) == 2
    assert len(deck) == 1
    assert drawn[0] != drawn[1]
