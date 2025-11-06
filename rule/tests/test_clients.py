from __future__ import annotations

import json
from typing import Any

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2] / "auto-card-IR-gen"))

import pytest
from auto_card_ir_gen.clients import PokemonTCGClient
from auto_card_ir_gen.exceptions import CardFetchError


class FakeResponse:
    def __init__(self, payload: Any) -> None:
        self._payload = payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # pragma: no cover - no cleanup needed
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


def test_search_card_builds_expected_query(monkeypatch):
    captured_url = {}

    def fake_urlopen(request, timeout=30):  # noqa: ANN001 - signature mirrors stdlib
        captured_url["url"] = request.full_url
        return FakeResponse({"data": [{"id": "sv1-1", "name": "Pidgey"}]})

    monkeypatch.setattr("auto_card_ir_gen.clients.urlopen", fake_urlopen)
    client = PokemonTCGClient(base_url="https://example.com")
    card = client.search_card("Pidgey", "MEW", "16")
    assert card["id"] == "sv1-1"
    url = captured_url["url"]
    assert "pageSize=1" in url
    assert "name%3A%22Pidgey%22" in url
    assert "%28set.id%3A%22MEW%22+OR+set.ptcgoCode%3A%22MEW%22%29" in url
    assert "number%3A%2216%22" in url


def test_search_card_raises_when_empty(monkeypatch):
    def fake_urlopen(request, timeout=30):  # noqa: ANN001 - signature mirrors stdlib
        return FakeResponse({"data": []})

    monkeypatch.setattr("auto_card_ir_gen.clients.urlopen", fake_urlopen)
    client = PokemonTCGClient(base_url="https://example.com")
    with pytest.raises(CardFetchError):
        client.search_card("Missing", "SET", "1")
