"""Unit tests for the Pokémon TCG synchronisation helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Sequence

import pytest

from core.pokemon_tcg_sync import (
    PokemonTCGSync,
    build_card_row,
    build_catalog_rows,
    build_set_row,
    dataclass_to_dict,
)


@dataclass
class DummyImages:
    symbol: str
    logo: str


@dataclass
class DummyLegality:
    unlimited: str | None
    expanded: str | None
    standard: str | None


@dataclass
class DummySet:
    id: str
    name: str
    series: str
    ptcgoCode: str | None
    releaseDate: str
    updatedAt: str
    total: int
    printedTotal: int
    images: DummyImages
    legalities: DummyLegality


@dataclass
class DummyCardSet:
    id: str


@dataclass
class DummyCard:
    id: str
    name: str
    supertype: str
    number: str
    rarity: str
    set: DummyCardSet


def test_dataclass_to_dict_preserves_nested_structures() -> None:
    dummy = DummySet(
        id="swsh1",
        name="Sword & Shield",
        series="Sword & Shield",
        ptcgoCode="SSH",
        releaseDate="2020/02/07",
        updatedAt="2024/01/01",
        total=202,
        printedTotal=200,
        images=DummyImages(symbol="symbol.png", logo="logo.png"),
        legalities=DummyLegality(unlimited="Legal", expanded="Legal", standard=None),
    )

    result = dataclass_to_dict(dummy)
    assert result["id"] == "swsh1"
    assert result["images"]["symbol"] == "symbol.png"
    assert result["legalities"]["expanded"] == "Legal"


def test_build_set_row_serialises_to_json() -> None:
    sync_ts = datetime.now(timezone.utc)
    dummy = DummySet(
        id="base1",
        name="Base Set",
        series="Base",
        ptcgoCode="BS",
        releaseDate="1999/01/09",
        updatedAt="2023/01/01",
        total=102,
        printedTotal=102,
        images=DummyImages(symbol="symbol", logo="logo"),
        legalities=DummyLegality(unlimited="Legal", expanded=None, standard=None),
    )

    row = build_set_row(dummy, sync_ts)
    assert row["id"] == "base1"
    payload = json.loads(row["data"])
    assert payload["name"] == "Base Set"
    assert row["last_synced_at"] == sync_ts


def test_build_card_row_extracts_set_identifier() -> None:
    sync_ts = datetime.now(timezone.utc)
    dummy = DummyCard(
        id="xy1-1",
        name="Venusaur-EX",
        supertype="Pokémon",
        number="1",
        rarity="Rare Holo EX",
        set=DummyCardSet(id="xy1"),
    )

    row = build_card_row(dummy, sync_ts)
    assert row["set_id"] == "xy1"
    payload = json.loads(row["data"])
    assert payload["name"] == "Venusaur-EX"


def test_build_catalog_rows_deduplicates_and_sorts() -> None:
    sync_ts = datetime.now(timezone.utc)
    rows = build_catalog_rows("type", ["Fire", "Water", "Fire"], sync_ts)
    assert [row["value"] for row in rows] == ["Fire", "Water"]
    assert all(json.loads(row["data"]) == {"value": row["value"]} for row in rows)


class StubSync(PokemonTCGSync):
    def __init__(self, pages: Dict[int, Sequence[int]]) -> None:
        super().__init__(connection=object(), page_size=2, max_card_pages=3)
        self._pages = pages

    def _fetch_card_page(self, page: int) -> Sequence[int]:  # type: ignore[override]
        return self._pages.get(page, [])


def test_iter_card_batches_respects_max_pages() -> None:
    pages: Dict[int, Sequence[int]] = {1: [1, 2], 2: [3], 3: [4], 4: [5]}
    syncer = StubSync(pages)
    batches = list(syncer._iter_card_batches())
    assert batches == [[1, 2], [3], [4]]


def test_pokemon_tcg_sync_rejects_invalid_page_size() -> None:
    with pytest.raises(ValueError):
        PokemonTCGSync(connection=object(), page_size=0)
