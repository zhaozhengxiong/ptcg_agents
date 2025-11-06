from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Tuple

import sys

sys.path.append(str(Path(__file__).resolve().parents[2] / "auto-card-IR-gen"))

import pytest

from auto_card_ir_gen import (
    PokemonTCGClient,
    RuleCompilationPipeline,
    RuleTemplateEngine,
    Storage,
)
from rules.engine import RuleEngine
from rules.schema import TriggerType


class _InMemoryDatabase:
    def __init__(self) -> None:
        self.sources: Dict[str, Dict[str, Any]] = {}
        self.rules: Dict[Tuple[str, str], Dict[str, Any]] = {}

    def connect(self) -> "_InMemoryConnection":
        return _InMemoryConnection(self)


class _InMemoryConnection:
    def __init__(self, db: _InMemoryDatabase) -> None:
        self.db = db

    # psycopg compat -----------------------------------------------------
    def execute(self, query: str, params: Optional[Tuple[Any, ...]] = None):
        cursor = _InMemoryCursor(self.db)
        cursor.execute(query, params)
        return cursor

    def commit(self) -> None:  # pragma: no cover - no-op for in-memory storage
        pass

    def rollback(self) -> None:  # pragma: no cover - no-op for in-memory storage
        pass

    def close(self) -> None:  # pragma: no cover - no-op for in-memory storage
        pass


class _InMemoryCursor:
    def __init__(self, db: _InMemoryDatabase) -> None:
        self.db = db
        self._rows: list[Dict[str, Any]] = []
        self.rowcount: int = -1

    def execute(self, query: str, params: Optional[Tuple[Any, ...]] = None):
        normalized = " ".join(query.split())
        params = params or tuple()
        if normalized.startswith("CREATE TABLE") or normalized.startswith("CREATE INDEX"):
            self.rowcount = 0
            self._rows = []
        elif normalized.startswith("INSERT INTO card_sources"):
            card_id, name, raw_payload, fetched_at, updated_at = params
            existing = self.db.sources.get(card_id)
            if existing is None:
                self.db.sources[card_id] = {
                    "card_id": card_id,
                    "name": name,
                    "raw_payload": raw_payload,
                    "fetched_at": fetched_at,
                    "updated_at": updated_at,
                }
            else:
                existing.update(
                    {
                        "name": name,
                        "raw_payload": raw_payload,
                        "updated_at": updated_at,
                    }
                )
            self.rowcount = 1
            self._rows = []
        elif normalized.startswith(
            "SELECT card_id, name, raw_payload, fetched_at, updated_at FROM card_sources"
        ):
            card_id = params[0]
            record = self.db.sources.get(card_id)
            self._rows = [record] if record else []
            self.rowcount = len(self._rows)
        elif normalized.startswith("INSERT INTO card_rules"):
            (
                card_id,
                rule_id,
                version,
                version_hash,
                payload,
                status,
                created_at,
                updated_at,
            ) = params
            key = (rule_id, version_hash)
            existing = self.db.rules.get(key)
            if existing is None:
                self.db.rules[key] = {
                    "card_id": card_id,
                    "rule_id": rule_id,
                    "version": version,
                    "version_hash": version_hash,
                    "payload": payload,
                    "status": status,
                    "reviewer": None,
                    "reviewed_at": None,
                    "created_at": created_at,
                    "updated_at": updated_at,
                }
            else:
                existing.update(
                    {
                        "payload": payload,
                        "status": status,
                        "updated_at": updated_at,
                    }
                )
            self.rowcount = 1
            self._rows = []
        elif normalized.startswith("UPDATE card_rules"):
            status, reviewer, reviewed_at, updated_at, rule_id, version_hash = params
            key = (rule_id, version_hash)
            existing = self.db.rules.get(key)
            if existing is None:
                self.rowcount = 0
                self._rows = []
            else:
                existing.update(
                    {
                        "status": status,
                        "reviewer": reviewer,
                        "reviewed_at": reviewed_at,
                        "updated_at": updated_at,
                    }
                )
                self.rowcount = 1
                self._rows = []
        elif normalized.startswith(
            "SELECT rule_id, version_hash, status, reviewer, reviewed_at FROM card_rules"
        ):
            rule_id, version_hash = params
            key = (rule_id, version_hash)
            record = self.db.rules.get(key)
            self._rows = [record] if record else []
            self.rowcount = len(self._rows)
        elif normalized.startswith(
            "SELECT card_id, rule_id, version, version_hash, payload, status, reviewer, reviewed_at, created_at, updated_at FROM card_rules WHERE"
        ):
            rule_id, version_hash = params
            key = (rule_id, version_hash)
            record = self.db.rules.get(key)
            self._rows = [record] if record else []
            self.rowcount = len(self._rows)
        elif normalized.startswith(
            "SELECT card_id, rule_id, version, version_hash, payload, status, reviewer, reviewed_at, created_at, updated_at FROM card_rules"
        ):
            self._rows = list(self.db.rules.values())
            self.rowcount = len(self._rows)
        else:  # pragma: no cover - ensure unsupported SQL is visible during failures
            raise NotImplementedError(f"Unsupported query: {query}")
        return self

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)


class FakeClient(PokemonTCGClient):
    def __init__(self, payload: Mapping[str, Any]) -> None:
        self.payload = payload

    def get_card(self, card_id: str) -> Mapping[str, Any]:
        return self.payload


@pytest.fixture()
def sample_card() -> Dict[str, Any]:
    return {
        "id": "sv1-1",
        "name": "Testmon",
        "set": {"id": "sv1", "releaseDate": "2023/01/01"},
        "number": "1",
        "abilities": [
            {
                "name": "Insight",
                "text": "Once during your turn, you may draw 2 cards.",
            }
        ],
    }


@pytest.fixture()
def storage():
    db = _InMemoryDatabase()
    store = Storage("postgresql://tests", connection_factory=db.connect)
    return store


def test_template_engine_extracts_draw_rule(sample_card: Dict[str, Any]) -> None:
    engine = RuleTemplateEngine()
    matches = engine.build_rules(sample_card)
    assert len(matches) == 1
    rule = matches[0].rule
    assert rule.trigger.type is TriggerType.MANUAL
    assert rule.modifiers[0].type == "once_per_turn"
    assert rule.effect.effect == "Draw"  # type: ignore[attr-defined]
    assert rule.effect.parameters["count"] == 2  # type: ignore[attr-defined]


def test_pipeline_persists_raw_and_rule(sample_card: Dict[str, Any], storage: Storage) -> None:
    pipeline = RuleCompilationPipeline(
        client=FakeClient(sample_card),
        storage=storage,
        template_engine=RuleTemplateEngine(),
        rule_engine=RuleEngine(),
    )
    result = pipeline.compile_card(sample_card["id"])
    assert result.card_id == sample_card["id"]
    assert result.rules[0].tests.passed is True
    source = storage.get_card_source(sample_card["id"])
    assert source is not None
    assert source.card_id == sample_card["id"]
    assert source.raw_payload["name"] == "Testmon"
    rule_record = storage.get_rule(result.rules[0].rule.rule_id, result.rules[0].version_hash)
    assert rule_record is not None
    assert rule_record.rule_id == result.rules[0].rule.rule_id
    assert rule_record.status == "draft"


def test_mark_rule_reviewed_updates_status(sample_card: Dict[str, Any], storage: Storage) -> None:
    pipeline = RuleCompilationPipeline(
        client=FakeClient(sample_card),
        storage=storage,
    )
    result = pipeline.compile_card(sample_card["id"])
    compiled = result.rules[0]
    updated = storage.mark_rule_reviewed(
        rule_id=compiled.rule.rule_id,
        version_hash=compiled.version_hash,
        reviewer="qa",
    )
    assert updated.status == "approved"
    assert updated.reviewer == "qa"
    assert updated.reviewed_at is not None


def test_mark_rule_reviewed_requires_existing_hash(sample_card: Dict[str, Any], storage: Storage) -> None:
    pipeline = RuleCompilationPipeline(
        client=FakeClient(sample_card),
        storage=storage,
    )
    pipeline.compile_card(sample_card["id"])
    with pytest.raises(Exception):
        storage.mark_rule_reviewed(rule_id="missing", version_hash="hash", reviewer="qa")
