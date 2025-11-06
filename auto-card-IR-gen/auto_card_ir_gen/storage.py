"""Database persistence helpers for card sources and compiled rules."""

from __future__ import annotations

import json
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, Iterable, Iterator, Optional

try:  # pragma: no cover - optional dependency for real PostgreSQL usage
    import psycopg
    from psycopg.rows import dict_row
except Exception:  # pragma: no cover - keep optional import silent
    psycopg = None  # type: ignore[assignment]
    dict_row = None  # type: ignore[assignment]

from .exceptions import ReviewError


@dataclass(slots=True)
class CardSourceRecord:
    """Persisted representation of a raw card payload."""

    card_id: str
    name: str
    raw_payload: Dict[str, Any]
    fetched_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class CardRuleRecord:
    """Persisted representation of a compiled rule."""

    card_id: str
    rule_id: str
    version: str
    version_hash: str
    payload: Dict[str, Any]
    status: str
    reviewer: Optional[str]
    reviewed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class StoredRule:
    """Lightweight DTO describing a persisted rule entry."""

    rule_id: str
    version_hash: str
    status: str
    reviewer: Optional[str]
    reviewed_at: Optional[datetime]


class Storage:
    """High level helper capable of persisting information into PostgreSQL databases."""

    def __init__(
        self,
        database_url: str,
        *,
        connection_factory: Optional[Callable[[], Any]] = None,
    ) -> None:
        if not database_url.startswith("postgres"):
            raise ValueError("Storage only supports PostgreSQL connection URLs")
        self._database_url = database_url
        self._connection_factory = connection_factory
        if self._connection_factory is None and psycopg is None:  # pragma: no cover - env guard
            raise RuntimeError(
                "psycopg is required for PostgreSQL storage but is not installed in this environment"
            )
        self._create_schema()

    # --------------------------------------------------------------- connections
    @contextmanager
    def _connection(self) -> Iterator[Any]:
        if self._connection_factory is not None:
            conn = self._connection_factory()
        else:  # pragma: no cover - requires psycopg at runtime
            assert psycopg is not None
            conn = psycopg.connect(self._database_url, row_factory=dict_row)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ------------------------------------------------------------------- schema
    def _create_schema(self) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS card_sources (
                    card_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    raw_payload TEXT NOT NULL,
                    fetched_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS card_rules (
                    card_id TEXT NOT NULL,
                    rule_id TEXT NOT NULL,
                    version TEXT NOT NULL,
                    version_hash TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    status TEXT NOT NULL,
                    reviewer TEXT,
                    reviewed_at TIMESTAMP,
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL,
                    PRIMARY KEY (rule_id, version_hash)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_card_rules_card_id ON card_rules(card_id)"
            )

    # ------------------------------------------------------------- card sources
    def upsert_card_source(self, payload: Dict[str, Any]) -> CardSourceRecord:
        card_id = str(payload.get("id"))
        if not card_id:
            raise ValueError("Pokemon card payload does not contain an 'id' field")
        name = str(payload.get("name", card_id))
        now = datetime.utcnow()
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO card_sources (card_id, name, raw_payload, fetched_at, updated_at)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT(card_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    raw_payload = EXCLUDED.raw_payload,
                    updated_at = EXCLUDED.updated_at
                """,
                (card_id, name, json.dumps(payload), now, now),
            )
            row = conn.execute(
                "SELECT card_id, name, raw_payload, fetched_at, updated_at FROM card_sources WHERE card_id = %s",
                (card_id,),
            ).fetchone()
        assert row is not None
        return CardSourceRecord(
            card_id=row["card_id"],
            name=row["name"],
            raw_payload=json.loads(row["raw_payload"]),
            fetched_at=_parse_timestamp(row["fetched_at"]),
            updated_at=_parse_timestamp(row["updated_at"]),
        )

    def get_card_source(self, card_id: str) -> Optional[CardSourceRecord]:
        with self._connection() as conn:
            row = conn.execute(
                "SELECT card_id, name, raw_payload, fetched_at, updated_at FROM card_sources WHERE card_id = %s",
                (card_id,),
            ).fetchone()
        if row is None:
            return None
        return CardSourceRecord(
            card_id=row["card_id"],
            name=row["name"],
            raw_payload=json.loads(row["raw_payload"]),
            fetched_at=_parse_timestamp(row["fetched_at"]),
            updated_at=_parse_timestamp(row["updated_at"]),
        )

    # --------------------------------------------------------------- rule storage
    def store_rule(
        self,
        *,
        card_id: str,
        rule_id: str,
        version: str,
        version_hash: str,
        payload: Dict[str, Any],
        status: str = "draft",
    ) -> StoredRule:
        now = datetime.utcnow()
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO card_rules (
                    card_id, rule_id, version, version_hash, payload, status, reviewer, reviewed_at, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, NULL, NULL, %s, %s)
                ON CONFLICT(rule_id, version_hash) DO UPDATE SET
                    payload = EXCLUDED.payload,
                    status = EXCLUDED.status,
                    updated_at = EXCLUDED.updated_at
                """,
                (card_id, rule_id, version, version_hash, json.dumps(payload), status, now, now),
            )
            row = conn.execute(
                """
                SELECT rule_id, version_hash, status, reviewer, reviewed_at
                FROM card_rules
                WHERE rule_id = %s AND version_hash = %s
                """,
                (rule_id, version_hash),
            ).fetchone()
        assert row is not None
        return StoredRule(
            rule_id=row["rule_id"],
            version_hash=row["version_hash"],
            status=row["status"],
            reviewer=row["reviewer"],
            reviewed_at=_parse_timestamp(row["reviewed_at"]) if row["reviewed_at"] else None,
        )

    def mark_rule_reviewed(
        self, *, rule_id: str, version_hash: str, reviewer: str, status: str = "approved"
    ) -> StoredRule:
        if not reviewer:
            raise ReviewError("Reviewer must be a non-empty string")
        now = datetime.utcnow()
        with self._connection() as conn:
            cursor = conn.execute(
                """
                UPDATE card_rules
                SET status = %s, reviewer = %s, reviewed_at = %s, updated_at = %s
                WHERE rule_id = %s AND version_hash = %s
                """,
                (status, reviewer, now, now, rule_id, version_hash),
            )
            if cursor.rowcount == 0:
                raise ReviewError(
                    f"Rule '{rule_id}' with hash '{version_hash}' does not exist in storage"
                )
            row = conn.execute(
                """
                SELECT rule_id, version_hash, status, reviewer, reviewed_at
                FROM card_rules
                WHERE rule_id = %s AND version_hash = %s
                """,
                (rule_id, version_hash),
            ).fetchone()
        assert row is not None
        return StoredRule(
            rule_id=row["rule_id"],
            version_hash=row["version_hash"],
            status=row["status"],
            reviewer=row["reviewer"],
            reviewed_at=_parse_timestamp(row["reviewed_at"]) if row["reviewed_at"] else None,
        )

    def get_rule(self, rule_id: str, version_hash: str) -> Optional[CardRuleRecord]:
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT card_id, rule_id, version, version_hash, payload, status, reviewer, reviewed_at, created_at, updated_at
                FROM card_rules
                WHERE rule_id = %s AND version_hash = %s
                """,
                (rule_id, version_hash),
            ).fetchone()
        if row is None:
            return None
        return CardRuleRecord(
            card_id=row["card_id"],
            rule_id=row["rule_id"],
            version=row["version"],
            version_hash=row["version_hash"],
            payload=json.loads(row["payload"]),
            status=row["status"],
            reviewer=row["reviewer"],
            reviewed_at=_parse_timestamp(row["reviewed_at"]) if row["reviewed_at"] else None,
            created_at=_parse_timestamp(row["created_at"]),
            updated_at=_parse_timestamp(row["updated_at"]),
        )

    def iter_rules(self) -> Iterable[CardRuleRecord]:
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT card_id, rule_id, version, version_hash, payload, status, reviewer, reviewed_at, created_at, updated_at FROM card_rules"
            ).fetchall()
        for row in rows:
            yield CardRuleRecord(
                card_id=row["card_id"],
                rule_id=row["rule_id"],
                version=row["version"],
                version_hash=row["version_hash"],
                payload=json.loads(row["payload"]),
                status=row["status"],
                reviewer=row["reviewer"],
                reviewed_at=_parse_timestamp(row["reviewed_at"]) if row["reviewed_at"] else None,
                created_at=_parse_timestamp(row["created_at"]),
                updated_at=_parse_timestamp(row["updated_at"]),
            )


def _parse_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    raise TypeError(f"Unsupported timestamp type: {type(value)!r}")


__all__ = [
    "Storage",
    "StoredRule",
    "CardSourceRecord",
    "CardRuleRecord",
]
