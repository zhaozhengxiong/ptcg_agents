"""HTTP client helpers to interact with the PokemonTCG.io API."""

from __future__ import annotations

import json
from typing import Any, List, Mapping, MutableMapping, Optional
from urllib.error import URLError
from urllib.request import Request, urlopen
from urllib.parse import urlencode

from .exceptions import CardFetchError


class PokemonTCGClient:
    """Simple wrapper around the public PokemonTCG.io REST API."""

    def __init__(
        self,
        *,
        base_url: str = "https://api.pokemontcg.io/v2",
        api_key: Optional[str] = None,
        headers: Optional[MutableMapping[str, str]] = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers: MutableMapping[str, str] = {"Accept": "application/json"}
        if headers:
            self._headers.update(headers)
        if api_key:
            self._headers["X-Api-Key"] = api_key

    # ------------------------------------------------------------------ utilities
    def get_card(self, card_id: str) -> Mapping[str, Any]:
        """Return the raw payload for a card identifier."""

        url = f"{self._base_url}/cards/{card_id}"
        request = Request(url, headers=dict(self._headers))
        try:
            with urlopen(request, timeout=30) as response:
                body = response.read().decode("utf-8")
        except URLError as exc:  # pragma: no cover - network failure safeguard
            raise CardFetchError(f"Failed to fetch card '{card_id}'") from exc
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive branch
            raise CardFetchError("PokemonTCG.io returned invalid JSON") from exc
        data = payload.get("data") if isinstance(payload, Mapping) else None
        if not isinstance(data, Mapping):
            raise CardFetchError("PokemonTCG.io response did not contain card data")
        return data

    def search_card(
        self,
        name: str,
        set_code: Optional[str] = None,
        number: Optional[str] = None,
        *,
        page_size: int = 1,
    ) -> Mapping[str, Any]:
        """Search for a card using a combination of name, set code and number."""

        if not name:
            raise ValueError("Card name must be provided when searching")

        query_parts: List[str] = [f'name:"{name}"']
        if set_code:
            query_parts.append(f'(set.id:"{set_code}" OR set.ptcgoCode:"{set_code}")')
        if number:
            query_parts.append(f'number:"{number}"')
        params = urlencode({"q": " ".join(query_parts), "pageSize": page_size})
        url = f"{self._base_url}/cards?{params}"
        request = Request(url, headers=dict(self._headers))
        try:
            with urlopen(request, timeout=30) as response:
                body = response.read().decode("utf-8")
        except URLError as exc:  # pragma: no cover - network failure safeguard
            raise CardFetchError("Failed to search for card") from exc
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive branch
            raise CardFetchError("PokemonTCG.io returned invalid JSON") from exc
        data = payload.get("data") if isinstance(payload, Mapping) else None
        if not isinstance(data, list) or not data:
            raise CardFetchError("PokemonTCG.io response did not include any cards")
        first = data[0]
        if not isinstance(first, Mapping):
            raise CardFetchError("PokemonTCG.io returned an unexpected card payload")
        return first


__all__ = ["PokemonTCGClient"]
