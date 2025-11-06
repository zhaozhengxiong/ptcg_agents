"""End-to-end pipeline turning card text into validated IR stored in PostgreSQL."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Iterable, List, Mapping, MutableMapping, Optional

from rules.engine import EffectContext, RuleEngine
from rules.schema import CardRule, Condition

from .clients import PokemonTCGClient
from .exceptions import CardFetchError
from .storage import StoredRule, Storage
from .templates import RuleTemplateEngine, TemplateMatch


@dataclass(slots=True)
class TestReport:
    """Represents the outcome of executing generated validation tests."""

    rule_id: str
    passed: bool
    details: Optional[str] = None


@dataclass(slots=True)
class CompiledRule:
    """A compiled rule and metadata produced by the pipeline."""

    rule: CardRule
    version_hash: str
    storage_record: StoredRule
    tests: TestReport


@dataclass(slots=True)
class CompilationResult:
    """Final result of running the compilation pipeline for a single card."""

    card_id: str
    raw_payload: Mapping[str, object]
    rules: List[CompiledRule]


class RuleCompilationPipeline:
    """Coordinates fetching, template matching, validation and persistence."""

    def __init__(
        self,
        *,
        client: PokemonTCGClient,
        storage: Storage,
        template_engine: Optional[RuleTemplateEngine] = None,
        rule_engine: Optional[RuleEngine] = None,
    ) -> None:
        self._client = client
        self._storage = storage
        self._templates = template_engine or RuleTemplateEngine()
        self._rule_engine = rule_engine or RuleEngine()

    # ------------------------------------------------------------------ pipeline
    def compile_card(self, card_id: str) -> CompilationResult:
        payload = self._client.get_card(card_id)
        if not isinstance(payload, Mapping):  # pragma: no cover - defensive
            raise CardFetchError(f"PokemonTCG.io returned unexpected payload for card '{card_id}'")
        self._storage.upsert_card_source(dict(payload))
        matches = self._templates.build_rules(payload)
        compiled_rules = [self._persist_rule(payload, match) for match in matches]
        return CompilationResult(card_id=card_id, raw_payload=payload, rules=compiled_rules)

    # ----------------------------------------------------------------- internals
    def _persist_rule(self, payload: Mapping[str, object], match: TemplateMatch) -> CompiledRule:
        rule = match.rule
        version_hash = _compute_hash(rule)
        storage_record = self._storage.store_rule(
            card_id=str(payload.get("id", "")),
            rule_id=rule.rule_id,
            version=rule.version,
            version_hash=version_hash,
            payload=rule.model_dump(mode="json"),
            status="draft",
        )
        test_report = self._run_tests(rule)
        return CompiledRule(rule=rule, version_hash=version_hash, storage_record=storage_record, tests=test_report)

    def _run_tests(self, rule: CardRule) -> TestReport:
        try:
            context = _build_test_context(rule)
            executed = self._rule_engine.execute(rule, context)
            if not executed:
                return TestReport(rule_id=rule.rule_id, passed=False, details="Trigger conditions not met")
            return TestReport(rule_id=rule.rule_id, passed=True)
        except Exception as exc:  # pragma: no cover - best effort reporting
            return TestReport(rule_id=rule.rule_id, passed=False, details=str(exc))


def _compute_hash(rule: CardRule) -> str:
    payload = rule.model_dump(mode="json")
    normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _build_test_context(rule: CardRule) -> EffectContext:
    state: MutableMapping[str, object] = {
        "players": {
            "player": {
                "deck": ["card-a", "card-b", "card-c"],
                "hand": [],
            }
        }
    }
    variables: MutableMapping[str, object] = {}
    if rule.trigger.type is not None and rule.trigger.type != rule.trigger.type.MANUAL:
        variables["event"] = rule.trigger.type.value
    if _requires_coin_flip(rule):
        variables.setdefault("coin_flip", "heads")
    context = EffectContext(
        controller="player",
        state=state,
        turn_identifier="turn-1",
        variables=variables,
    )
    return context


def _requires_coin_flip(rule: CardRule) -> bool:
    stack: List = [rule.effect]
    while stack:
        node = stack.pop()
        if hasattr(node, "condition") and isinstance(getattr(node, "condition"), Condition):
            condition = getattr(node, "condition")
            if getattr(condition, "path", "").endswith("coin_flip"):
                return True
        if hasattr(node, "if_true"):
            stack.append(getattr(node, "if_true"))
        if hasattr(node, "if_false") and getattr(node, "if_false") is not None:
            stack.append(getattr(node, "if_false"))
        if hasattr(node, "steps"):
            stack.extend(getattr(node, "steps"))
    return False


__all__ = [
    "RuleCompilationPipeline",
    "CompilationResult",
    "CompiledRule",
    "TestReport",
]
