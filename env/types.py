"""Common dataclasses shared by environment implementations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class StepResult:
    """Container for the result of an environment step."""

    state: Dict[str, Any]
    reward: float
    done: bool
    info: Dict[str, Any]


__all__ = ["StepResult"]
