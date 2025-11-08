"""Minimal subset of the :mod:`dacite` API required by pokemontcgsdk.

This project vendors a light-weight implementation of :func:`from_dict`
from the `dacite` package so that we can run the Pokémon TCG sync tool in
environments where installing third party dependencies is not possible.

The implementation intentionally supports only the behaviours exercised by
``pokemontcgsdk``:

* instantiating dataclasses from dictionaries
* recursively converting nested dataclasses
* handling ``Optional`` fields
* coercing lists, tuples, and dictionaries

It is **not** a drop-in replacement for the real library, but it keeps the
tool operational without requiring additional packages.
"""

from __future__ import annotations

from dataclasses import MISSING, fields, is_dataclass
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Sequence
from typing import Tuple, Type, TypeVar, Union, get_args, get_origin

T = TypeVar("T")

__all__ = ["from_dict"]


def from_dict(data_class: Type[T], data: Mapping[str, Any]) -> T:
    """Instantiate ``data_class`` from ``data``.

    Parameters
    ----------
    data_class:
        A dataclass type that should be instantiated.
    data:
        A mapping containing the field values for the dataclass.
    """

    if not is_dataclass(data_class):  # pragma: no cover - sanity guard
        raise TypeError("from_dict() expects a dataclass type")

    kwargs: Dict[str, Any] = {}
    for field in fields(data_class):
        if field.name in data:
            value = data[field.name]
        elif field.default is not MISSING:
            continue
        elif field.default_factory is not MISSING:  # type: ignore[comparison-overlap]
            continue
        else:
            value = None

        kwargs[field.name] = _convert_value(field.type, value)

    return data_class(**kwargs)  # type: ignore[call-arg]


def _convert_value(expected_type: Any, value: Any) -> Any:
    if value is None:
        return None

    origin = get_origin(expected_type)
    args = get_args(expected_type)

    if expected_type in (Any, object):
        return value

    if origin is Union:
        non_none_args = [arg for arg in args if arg is not type(None)]
        for arg in non_none_args:
            try:
                return _convert_value(arg, value)
            except (TypeError, ValueError):
                continue
        return value

    if origin in (list, List, Sequence, Iterable):  # type: ignore[name-defined]
        item_type = args[0] if args else Any
        return [_convert_value(item_type, item) for item in value]

    if origin in (tuple, Tuple):
        item_type = args[0] if args else Any
        return tuple(_convert_value(item_type, item) for item in value)

    if origin in (dict, Dict, Mapping, MutableMapping):  # type: ignore[name-defined]
        key_type = args[0] if args else Any
        value_type = args[1] if len(args) > 1 else Any
        return {
            _convert_value(key_type, key): _convert_value(value_type, val)
            for key, val in value.items()
        }

    if is_dataclass(expected_type):
        if isinstance(value, Mapping):
            return from_dict(expected_type, value)
        raise TypeError(
            f"Cannot construct dataclass {expected_type!r} from non-mapping value"
        )

    try:
        if isinstance(value, expected_type):
            return value
    except TypeError:
        # ``expected_type`` can be typing objects that are not suitable for
        # ``isinstance`` checks (e.g. ``typing.Any``). In that case we simply
        # return the original value.
        return value

    if expected_type in (Any, object):
        return value

    try:
        return expected_type(value)  # type: ignore[call-arg]
    except Exception as exc:  # pragma: no cover - fallback for unexpected types
        raise TypeError(f"Unable to convert value {value!r} to {expected_type!r}") from exc
