"""Helpers for loading and caching IR rules from external sources."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional

from .errors import IRValidationError, RuleNotFoundError, RuleVersionMismatchError
from .schema import CardRule, CardRuleCollection


class RuleRepository:
    """In-memory registry of :class:`CardRule` objects with simple caching."""

    def __init__(self) -> None:
        self._rules: Dict[str, CardRule] = {}
        self._json_cache: Dict[Path, float] = {}

    # ------------------------------------------------------------------ loading
    def load_from_json(self, path: Path, *, force: bool = False) -> None:
        """Load rules from a JSON file on disk."""

        path = Path(path)
        current_timestamp = path.stat().st_mtime_ns
        if not force and path in self._json_cache and self._json_cache[path] >= current_timestamp:
            return
        payload = json.loads(path.read_text())
        self._store_collection(payload)
        self._json_cache[path] = current_timestamp

    def load_from_records(self, records: Iterable[Mapping[str, Any]]) -> None:
        """Load rules from database-like rows."""

        for record in records:
            payload = dict(record)
            data = payload.pop("payload", payload)
            if not isinstance(data, Mapping):
                raise IRValidationError("Database record payload must be a mapping")
            rule = CardRule.model_validate(data)
            if "version" in payload and rule.version != payload["version"]:
                raise RuleVersionMismatchError(rule.rule_id, payload["version"], rule.version)
            self._rules[rule.rule_id] = rule

    # ------------------------------------------------------------------- access
    def get(self, rule_id: str, *, version: Optional[str] = None) -> CardRule:
        try:
            rule = self._rules[rule_id]
        except KeyError as exc:  # pragma: no cover - defensive branch
            raise RuleNotFoundError(rule_id) from exc
        if version is not None and rule.version != version:
            raise RuleVersionMismatchError(rule_id, version, rule.version)
        return rule

    def _store_collection(self, payload: Any) -> None:
        if isinstance(payload, Mapping) and "rules" in payload:
            payload = payload["rules"]
        collection = CardRuleCollection.model_validate(payload)
        for rule in collection.root:
            self._rules[rule.rule_id] = rule


__all__ = ["RuleRepository"]
