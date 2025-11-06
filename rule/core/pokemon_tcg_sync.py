"""Utilities for syncing Pokémon TCG data into PostgreSQL."""

from __future__ import annotations

import argparse
import json
import logging
import os
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterator, List, Mapping, MutableMapping, Optional, Sequence

try:  # pragma: no cover - allow importing without psycopg installed
    import psycopg  # type: ignore[unused-ignore]
except ModuleNotFoundError:  # pragma: no cover - handled at runtime for CLI usage
    psycopg = None  # type: ignore[assignment]

if TYPE_CHECKING:  # pragma: no cover
    from psycopg import Connection
else:  # pragma: no cover
    Connection = Any

SDK_AVAILABLE = False

try:
    from pokemontcgsdk import Card, Rarity, RestClient, Set, Subtype, Supertype, Type
    SDK_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover - fallback for local path installs
    import sys

    SDK_PATH = Path(__file__).resolve().parents[2] / "pokemon-tcg-sdk-python-master"
    if SDK_PATH.exists():
        sys.path.append(str(SDK_PATH))
        try:
            from pokemontcgsdk import Card, Rarity, RestClient, Set, Subtype, Supertype, Type
            SDK_AVAILABLE = True
        except ModuleNotFoundError:
            Card = Set = Type = Subtype = Supertype = Rarity = Any  # type: ignore[assignment]
            RestClient = None  # type: ignore[assignment]
    else:  # pragma: no cover - surfaced during import errors
        Card = Set = Type = Subtype = Supertype = Rarity = Any  # type: ignore[assignment]
        RestClient = None  # type: ignore[assignment]


LOGGER = logging.getLogger(__name__)

SET_UPSERT_SQL = """
INSERT INTO pokemon_sets (
    id,
    name,
    series,
    ptcgo_code,
    release_date,
    updated_at,
    total,
    printed_total,
    data,
    last_synced_at
) VALUES (
    %(id)s,
    %(name)s,
    %(series)s,
    %(ptcgo_code)s,
    %(release_date)s,
    %(updated_at)s,
    %(total)s,
    %(printed_total)s,
    %(data)s::jsonb,
    %(last_synced_at)s
) ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    series = EXCLUDED.series,
    ptcgo_code = EXCLUDED.ptcgo_code,
    release_date = EXCLUDED.release_date,
    updated_at = EXCLUDED.updated_at,
    total = EXCLUDED.total,
    printed_total = EXCLUDED.printed_total,
    data = EXCLUDED.data,
    last_synced_at = EXCLUDED.last_synced_at
"""

CARD_UPSERT_SQL = """
INSERT INTO pokemon_cards (
    id,
    name,
    supertype,
    number,
    rarity,
    set_id,
    data,
    last_synced_at
) VALUES (
    %(id)s,
    %(name)s,
    %(supertype)s,
    %(number)s,
    %(rarity)s,
    %(set_id)s,
    %(data)s::jsonb,
    %(last_synced_at)s
) ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    supertype = EXCLUDED.supertype,
    number = EXCLUDED.number,
    rarity = EXCLUDED.rarity,
    set_id = EXCLUDED.set_id,
    data = EXCLUDED.data,
    last_synced_at = EXCLUDED.last_synced_at
"""

CATALOG_UPSERT_SQL = """
INSERT INTO pokemon_catalog_values (
    category,
    value,
    data,
    last_synced_at
) VALUES (
    %(category)s,
    %(value)s,
    %(data)s::jsonb,
    %(last_synced_at)s
) ON CONFLICT (category, value) DO UPDATE SET
    data = EXCLUDED.data,
    last_synced_at = EXCLUDED.last_synced_at
"""


def build_set_row(set_obj: Set, sync_ts: datetime) -> MutableMapping[str, object]:
    """Create a mapping suitable for the set upsert query."""

    data = dataclass_to_dict(set_obj)
    return {
        "id": getattr(set_obj, "id", None),
        "name": getattr(set_obj, "name", None),
        "series": getattr(set_obj, "series", None),
        "ptcgo_code": getattr(set_obj, "ptcgoCode", None),
        "release_date": getattr(set_obj, "releaseDate", None),
        "updated_at": getattr(set_obj, "updatedAt", None),
        "total": getattr(set_obj, "total", None),
        "printed_total": getattr(set_obj, "printedTotal", None),
        "data": json.dumps(data),
        "last_synced_at": sync_ts,
    }


def build_card_row(card_obj: Card, sync_ts: datetime) -> MutableMapping[str, object]:
    """Create a mapping suitable for the card upsert query."""

    data = dataclass_to_dict(card_obj)
    set_info = getattr(card_obj, "set", None)
    set_id = getattr(set_info, "id", None) if set_info is not None else None

    return {
        "id": getattr(card_obj, "id", None),
        "name": getattr(card_obj, "name", None),
        "supertype": getattr(card_obj, "supertype", None),
        "number": getattr(card_obj, "number", None),
        "rarity": getattr(card_obj, "rarity", None),
        "set_id": set_id,
        "data": json.dumps(data),
        "last_synced_at": sync_ts,
    }


def build_catalog_rows(
    category: str, values: Sequence[str], sync_ts: datetime
) -> List[MutableMapping[str, object]]:
    """Create rows for catalog style resources such as types or rarities."""

    rows: List[MutableMapping[str, object]] = []
    for value in sorted(set(values)):
        rows.append(
            {
                "category": category,
                "value": value,
                "data": json.dumps({"value": value}),
                "last_synced_at": sync_ts,
            }
        )

    return rows


def dataclass_to_dict(instance: object) -> Mapping[str, object]:
    """Convert a dataclass instance into a plain dictionary."""

    if is_dataclass(instance):
        return asdict(instance)
    raise TypeError(f"Expected a dataclass instance, received: {type(instance)!r}")


class PokemonTCGSync:
    """Synchronise Pokémon TCG data from pokemontcgsdk into PostgreSQL."""

    def __init__(
        self,
        connection: Connection,
        *,
        page_size: int = 250,
        max_card_pages: Optional[int] = None,
    ) -> None:
        if page_size <= 0:
            raise ValueError("page_size must be a positive integer")

        self._connection = connection
        self._page_size = page_size
        self._max_card_pages = max_card_pages

    def sync(self) -> None:
        """Synchronise sets, cards, and metadata tables."""

        if not SDK_AVAILABLE:
            raise RuntimeError(
                "pokemontcgsdk is required to sync data. Ensure its dependencies are installed."
            )

        sync_ts = datetime.now(timezone.utc)
        LOGGER.info("Starting Pokémon TCG sync at %s", sync_ts.isoformat())

        self._ensure_tables()
        self._sync_sets(sync_ts)
        self._sync_catalogs(sync_ts)
        self._sync_cards(sync_ts)

    # ------------------------------------------------------------------
    # Table management
    # ------------------------------------------------------------------
    def _ensure_tables(self) -> None:
        LOGGER.debug("Ensuring Pokémon TCG tables exist")
        with self._connection.transaction():
            with self._connection.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS pokemon_sets (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        series TEXT,
                        ptcgo_code TEXT,
                        release_date TEXT,
                        updated_at TEXT,
                        total INTEGER,
                        printed_total INTEGER,
                        data JSONB NOT NULL,
                        last_synced_at TIMESTAMPTZ NOT NULL
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS pokemon_cards (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        supertype TEXT,
                        number TEXT,
                        rarity TEXT,
                        set_id TEXT,
                        data JSONB NOT NULL,
                        last_synced_at TIMESTAMPTZ NOT NULL
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS pokemon_catalog_values (
                        category TEXT NOT NULL,
                        value TEXT NOT NULL,
                        data JSONB NOT NULL,
                        last_synced_at TIMESTAMPTZ NOT NULL,
                        PRIMARY KEY (category, value)
                    )
                    """
                )

    # ------------------------------------------------------------------
    # Set synchronisation
    # ------------------------------------------------------------------
    def _sync_sets(self, sync_ts: datetime) -> None:
        LOGGER.info("Fetching Pokémon TCG sets")
        sets = Set.all()
        LOGGER.info("Fetched %d sets", len(sets))

        rows = [build_set_row(item, sync_ts) for item in sets]

        with self._connection.transaction():
            with self._connection.cursor() as cursor:
                if rows:
                    cursor.executemany(SET_UPSERT_SQL, rows)
                cursor.execute(
                    "DELETE FROM pokemon_sets WHERE last_synced_at < %s",
                    (sync_ts,),
                )

    # ------------------------------------------------------------------
    # Metadata synchronisation
    # ------------------------------------------------------------------
    def _sync_catalogs(self, sync_ts: datetime) -> None:
        LOGGER.info("Fetching Pokémon TCG catalog metadata")
        catalog_sources = {
            "type": Type.all(),
            "supertype": Supertype.all(),
            "subtype": Subtype.all(),
            "rarity": Rarity.all(),
        }

        with self._connection.transaction():
            with self._connection.cursor() as cursor:
                for category, values in catalog_sources.items():
                    LOGGER.info("Upserting %d values for %s", len(values), category)
                    rows = build_catalog_rows(category, values, sync_ts)
                    if rows:
                        cursor.executemany(CATALOG_UPSERT_SQL, rows)
                cursor.execute(
                    "DELETE FROM pokemon_catalog_values WHERE last_synced_at < %s",
                    (sync_ts,),
                )

    # ------------------------------------------------------------------
    # Card synchronisation
    # ------------------------------------------------------------------
    def _sync_cards(self, sync_ts: datetime) -> None:
        total_cards = 0
        for page, batch in enumerate(self._iter_card_batches(), start=1):
            LOGGER.info("Upserting %d cards from page %d", len(batch), page)
            rows = [build_card_row(card_obj, sync_ts) for card_obj in batch]
            with self._connection.transaction():
                with self._connection.cursor() as cursor:
                    if rows:
                        cursor.executemany(CARD_UPSERT_SQL, rows)
            total_cards += len(batch)

        LOGGER.info("Upserted %d cards", total_cards)

        with self._connection.transaction():
            with self._connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM pokemon_cards WHERE last_synced_at < %s",
                    (sync_ts,),
                )

    def _iter_card_batches(self) -> Iterator[Sequence[Card]]:
        page = 1
        while True:
            if self._max_card_pages is not None and page > self._max_card_pages:
                break

            batch = self._fetch_card_page(page)
            if not batch:
                break

            yield batch
            page += 1

    def _fetch_card_page(self, page: int) -> Sequence[Card]:
        LOGGER.debug("Fetching cards page %d with size %d", page, self._page_size)
        return Card.where(page=page, pageSize=self._page_size)


def configure_rest_client(api_key: Optional[str]) -> None:
    """Configure the pokemontcgsdk REST client with the provided API key."""

    if not SDK_AVAILABLE:
        raise RuntimeError(
            "pokemontcgsdk is not available. Install it before configuring the REST client."
        )

    if api_key and RestClient is not None:
        RestClient.configure(api_key=api_key)


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sync Pokémon TCG data into PostgreSQL")
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL"),
        help="SQLAlchemy-style database URL to the PostgreSQL instance",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("POKEMONTCG_IO_API_KEY"),
        help="API key for pokemontcg.io (optional but recommended)",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=int(os.getenv("POKEMONTCG_SYNC_PAGE_SIZE", "250")),
        help="Number of cards to request per page",
    )
    parser.add_argument(
        "--max-card-pages",
        type=int,
        default=None,
        help="Limit the number of card pages fetched (useful for testing)",
    )
    return parser


def run_from_cli(argv: Optional[Sequence[str]] = None) -> None:
    parser = build_argument_parser()
    args = parser.parse_args(argv)

    if not args.database_url:
        parser.error(
            "A database URL must be provided via --database-url or the DATABASE_URL environment variable."
        )

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    configure_rest_client(args.api_key)

    LOGGER.info("Connecting to PostgreSQL")
    if psycopg is None:
        raise RuntimeError(
            "psycopg is required to run the sync tool. Please install it via Poetry or pip before executing the script."
        )

    with psycopg.connect(args.database_url) as connection:
        syncer = PokemonTCGSync(
            connection,
            page_size=args.page_size,
            max_card_pages=args.max_card_pages,
        )
        syncer.sync()


__all__ = [
    "PokemonTCGSync",
    "build_argument_parser",
    "build_card_row",
    "build_catalog_rows",
    "build_set_row",
    "configure_rest_client",
    "dataclass_to_dict",
    "run_from_cli",
]
