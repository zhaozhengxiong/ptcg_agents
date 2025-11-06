"""Utilities that centralise the project's randomness handling."""

from __future__ import annotations

import hashlib
import json
import os
import random
from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass(frozen=True)
class RNGSnapshot:
    """Serializable snapshot of the current RNG configuration."""

    seed: Optional[int]
    python_state: object
    numpy_state: tuple
    generator_state: dict[str, object]


_GLOBAL_SEED: Optional[int] = None
_GLOBAL_SEED_SEQUENCE: np.random.SeedSequence = np.random.SeedSequence()
_GLOBAL_GENERATOR: np.random.Generator = np.random.Generator(np.random.PCG64())


def seed_everything(seed: Optional[int]) -> RNGSnapshot:
    """Seed Python's ``random`` module and NumPy with a single value.

    Parameters
    ----------
    seed:
        The value to seed every RNG with.  When *None*, a seed derived from
        :func:`os.urandom` is used which keeps the RNGs in a valid state but
        does not guarantee reproducibility.
    """

    global _GLOBAL_SEED, _GLOBAL_SEED_SEQUENCE, _GLOBAL_GENERATOR

    if seed is None:
        seed = int.from_bytes(os.urandom(8), "big")

    _GLOBAL_SEED = int(seed)
    random.seed(seed)
    np.random.seed(seed)
    _GLOBAL_SEED_SEQUENCE = np.random.SeedSequence(seed)
    _GLOBAL_GENERATOR = np.random.Generator(np.random.PCG64(_GLOBAL_SEED_SEQUENCE))
    return snapshot()


def snapshot() -> RNGSnapshot:
    """Return a :class:`RNGSnapshot` describing the current global RNG state."""

    return RNGSnapshot(
        seed=_GLOBAL_SEED,
        python_state=random.getstate(),
        numpy_state=np.random.get_state(),
        generator_state=_GLOBAL_GENERATOR.bit_generator.state,
    )


def global_rng() -> np.random.Generator:
    """Return the shared NumPy generator used across the project."""

    return _GLOBAL_GENERATOR


def spawn_seed_sequence() -> np.random.SeedSequence:
    """Return a child seed sequence derived from the global configuration."""

    return _GLOBAL_SEED_SEQUENCE.spawn(1)[0]


def generator_from_seed_sequence(seed_sequence: np.random.SeedSequence) -> np.random.Generator:
    """Create a new generator initialised with ``seed_sequence``."""

    return np.random.Generator(np.random.PCG64(seed_sequence))


def rng_state_digest() -> str:
    """Return a SHA256 digest representing the current RNG state."""

    snap = snapshot()
    hasher = hashlib.sha256()
    hasher.update(json.dumps(snap.seed).encode("utf8"))
    hasher.update(repr(snap.python_state).encode("utf8"))
    hasher.update(json.dumps(snap.numpy_state, default=_json_default).encode("utf8"))
    hasher.update(json.dumps(snap.generator_state, sort_keys=True).encode("utf8"))
    return hasher.hexdigest()


def generator_state_digest(generator: np.random.Generator) -> str:
    """Return a SHA256 digest of ``generator``'s internal state."""

    state = generator.bit_generator.state
    return hashlib.sha256(json.dumps(state, sort_keys=True).encode("utf8")).hexdigest()


def _json_default(obj: object) -> object:
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    raise TypeError(f"Object of type {type(obj)!r} is not JSON serialisable")


__all__ = [
    "RNGSnapshot",
    "generator_from_seed_sequence",
    "generator_state_digest",
    "global_rng",
    "rng_state_digest",
    "seed_everything",
    "snapshot",
    "spawn_seed_sequence",
]

