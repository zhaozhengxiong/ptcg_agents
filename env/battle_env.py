"""Minimal battle environment implementing the legal action mask system."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional

from core.errors import IllegalActionError
from core.state_machine import ActionType, BattleStateMachine, Phase, StateSnapshot
from env.types import StepResult


@dataclass(frozen=True)
class ActionSpec:
    """Metadata describing an action that can appear in the mask."""

    action_type: ActionType
    allowed_phases: Iterable[Phase]
    description: str
    max_uses_per_turn: Optional[int] = None

    def to_payload(self) -> Dict[str, object]:
        constraints: Dict[str, object] = {}
        if self.max_uses_per_turn is not None:
            constraints["max_uses_per_turn"] = self.max_uses_per_turn
        return {
            "action_type": self.action_type.name,
            "description": self.description,
            "phase": [phase.name for phase in self.allowed_phases],
            "constraints": constraints,
        }


@dataclass
class TurnTracker:
    """Tracks once-per-turn limitations for actions."""

    turn_number: int = 0
    usage: Dict[ActionType, int] = field(default_factory=dict)

    def reset(self, *, turn_number: int) -> None:
        self.turn_number = turn_number
        self.usage.clear()

    def mark_used(self, action_type: ActionType) -> None:
        self.usage[action_type] = self.usage.get(action_type, 0) + 1

    def usage_count(self, action_type: ActionType) -> int:
        return self.usage.get(action_type, 0)


class ActionRulebook:
    """Encapsulates the environment's legal action logic."""

    def __init__(self) -> None:
        main_phase = (Phase.MAIN_PHASE,)
        self._specs: Dict[ActionType, ActionSpec] = {
            ActionType.PLAY_CARD: ActionSpec(
                ActionType.PLAY_CARD,
                main_phase,
                "Play a card from the hand.",
            ),
            ActionType.ATTACH_ENERGY: ActionSpec(
                ActionType.ATTACH_ENERGY,
                main_phase,
                "Attach one basic Energy card from hand to a Pokémon.",
                max_uses_per_turn=1,
            ),
            ActionType.USE_ABILITY: ActionSpec(
                ActionType.USE_ABILITY,
                main_phase,
                "Use an Ability printed on a Pokémon in play.",
            ),
            ActionType.RETREAT: ActionSpec(
                ActionType.RETREAT,
                main_phase,
                "Retreat the Active Pokémon by paying its retreat cost.",
                max_uses_per_turn=1,
            ),
            ActionType.DECLARE_ATTACK: ActionSpec(
                ActionType.DECLARE_ATTACK,
                main_phase,
                "Declare an attack for the turn.",
                max_uses_per_turn=1,
            ),
            ActionType.END_TURN: ActionSpec(
                ActionType.END_TURN,
                main_phase,
                "End the current turn.",
                max_uses_per_turn=1,
            ),
            ActionType.PASS: ActionSpec(
                ActionType.PASS,
                main_phase,
                "Pass priority without performing an action.",
            ),
        }

    def legal_actions(self, snapshot: StateSnapshot, tracker: TurnTracker) -> List[ActionSpec]:
        actions: List[ActionSpec] = []
        for spec in self._specs.values():
            if snapshot.phase not in spec.allowed_phases:
                continue
            if spec.max_uses_per_turn is not None:
                if tracker.usage_count(spec.action_type) >= spec.max_uses_per_turn:
                    continue
            actions.append(spec)
        return actions

    def validate(self, snapshot: StateSnapshot, tracker: TurnTracker, action: Dict[str, object]) -> ActionSpec:
        if not isinstance(action, dict):
            raise IllegalActionError("Action must be provided as a dictionary.")
        raw_type = action.get("action_type")
        if not isinstance(raw_type, str):
            raise IllegalActionError("Action dictionary requires the 'action_type' field.")
        try:
            action_type = ActionType[raw_type]
        except KeyError:
            raise IllegalActionError(f"Unknown action type: {raw_type!r}.")
        spec = self._specs.get(action_type)
        if spec is None:
            raise IllegalActionError(f"Action {raw_type!r} is not supported by the environment.")
        if snapshot.phase not in spec.allowed_phases:
            raise IllegalActionError(
                f"Action {raw_type} is not legal during phase {snapshot.phase.name}."
            )
        if spec.max_uses_per_turn is not None and tracker.usage_count(action_type) >= spec.max_uses_per_turn:
            raise IllegalActionError(
                f"Action {raw_type} already reached its per-turn limit of {spec.max_uses_per_turn}."
            )
        return spec


class BattleEnv:
    """Simplified environment that exposes legal action masking."""

    def __init__(self, *, rulebook: Optional[ActionRulebook] = None) -> None:
        self._state_machine = BattleStateMachine()
        self._rulebook = rulebook or ActionRulebook()
        self._turn_tracker = TurnTracker()
        self._snapshot: StateSnapshot = self._state_machine.snapshot()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def reset(self) -> Dict[str, object]:
        self._state_machine.reset()
        self._turn_tracker.reset(turn_number=0)
        self._refresh_snapshot()
        self._auto_advance()
        return self._build_observation()

    def legal_actions(self) -> List[Dict[str, object]]:
        specs = self._rulebook.legal_actions(self._snapshot, self._turn_tracker)
        return [spec.to_payload() for spec in specs]

    def step(self, action: Dict[str, object]) -> StepResult:
        if self._snapshot.phase == Phase.GAME_END:
            return StepResult(self._build_observation(), 0.0, True, {"message": "game already finished"})

        spec = self._rulebook.validate(self._snapshot, self._turn_tracker, action)
        self._turn_tracker.mark_used(spec.action_type)

        self._state_machine.advance(spec.action_type)
        self._refresh_snapshot()
        self._auto_advance()

        observation = self._build_observation()
        done = self._snapshot.phase == Phase.GAME_END
        return StepResult(observation, 0.0, done, {})

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _refresh_snapshot(self) -> None:
        self._snapshot = self._state_machine.snapshot()
        if self._turn_tracker.turn_number != self._snapshot.turn_number:
            self._turn_tracker.reset(turn_number=self._snapshot.turn_number)

    def _auto_advance(self) -> None:
        while True:
            legal = self._rulebook.legal_actions(self._snapshot, self._turn_tracker)
            if legal or self._snapshot.phase == Phase.GAME_END:
                break
            self._state_machine.advance()
            self._refresh_snapshot()

    def _build_observation(self) -> Dict[str, object]:
        return {
            "phase": self._snapshot.phase.name,
            "turn": self._snapshot.turn_number,
            "active_player": self._snapshot.active_player.name,
            "legal_actions": self.legal_actions(),
        }


__all__ = ["ActionRulebook", "ActionSpec", "BattleEnv", "TurnTracker"]
