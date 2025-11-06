import json
from pathlib import Path

import pytest

from rules.errors import RuleVersionMismatchError
from rules.loader import RuleRepository


def sample_rule_payload(version: str = "1.0") -> dict:
    return {
        "rule_id": "draw.rule",
        "name": "Draw",
        "version": version,
        "trigger": {"type": "manual"},
        "effect": {"type": "atomic", "effect": "Draw", "parameters": {"count": 1}},
    }


def test_load_from_json_and_cache(tmp_path: Path) -> None:
    repo = RuleRepository()
    json_path = tmp_path / "rules.json"
    json_path.write_text(json.dumps([sample_rule_payload("1.0")]))
    repo.load_from_json(json_path)
    assert repo.get("draw.rule").version == "1.0"
    json_path.write_text(json.dumps([sample_rule_payload("2.0")]))
    repo.load_from_json(json_path)
    assert repo.get("draw.rule").version == "1.0"
    repo.load_from_json(json_path, force=True)
    assert repo.get("draw.rule").version == "2.0"


def test_load_from_records_validates_version() -> None:
    repo = RuleRepository()
    repo.load_from_records([{ "payload": sample_rule_payload("1.0"), "version": "1.0" }])
    assert repo.get("draw.rule").version == "1.0"
    with pytest.raises(RuleVersionMismatchError):
        repo.load_from_records([{ "payload": sample_rule_payload("1.0"), "version": "2.0" }])
