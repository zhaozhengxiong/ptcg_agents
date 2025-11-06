"""Minimal battle environment implementing the legal action mask system."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Dict, Iterable, List, Optional

import numpy as np

from core.errors import IllegalActionError
from core.random_control import generator_from_seed_sequence, spawn_seed_sequence
from core.state_machine import ActionType, BattleStateMachine, Phase, PlayerSide, StateSnapshot
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


@dataclass
class PlayerProgress:
    """Aggregated battle statistics for a player."""

    prizes_taken: int = 0
    knockouts: int = 0


@dataclass(frozen=True)
class RewardConfig:
    """Tunable reward constants used by :class:`BattleEnv`."""

    prizes_to_win: int = 6
    damage_per_attack: int = 30
    damage_to_knockout: int = 60
    damage_reward: float = 0.1
    prize_reward: float = 0.2
    win_reward: float = 1.0


class BattleEnv:
    """Simplified environment that exposes legal action masking."""

    def __init__(
        self,
        *,
        rulebook: Optional[ActionRulebook] = None,
        reward_config: RewardConfig | None = None,
        seed: Optional[int] = None,
    ) -> None:
        self._state_machine = BattleStateMachine()
        self._rulebook = rulebook or ActionRulebook()
        self._turn_tracker = TurnTracker()
        self._snapshot: StateSnapshot = self._state_machine.snapshot()
        self._reward_config = reward_config or RewardConfig()
        self._progress: Dict[PlayerSide, PlayerProgress] = {}
        self._damage_counters: Dict[PlayerSide, int] = {}
        self._pending_reward: float = 0.0
        self._winner: Optional[PlayerSide] = None
        self._seed_sequence = (
            np.random.SeedSequence(seed) if seed is not None else spawn_seed_sequence()
        )
        self._rng = generator_from_seed_sequence(self._seed_sequence)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def reset(self) -> Dict[str, object]:
        self._rng = generator_from_seed_sequence(self._seed_sequence)
        self._state_machine.reset()
        self._turn_tracker.reset(turn_number=0)
        self._refresh_snapshot()
        self._progress = {player: PlayerProgress() for player in PlayerSide}
        self._damage_counters = {player: 0 for player in PlayerSide}
        self._pending_reward = 0.0
        self._winner = None
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
        reward = self._consume_pending_reward()
        info = self._build_info(done)
        return StepResult(observation, reward, done, info)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _refresh_snapshot(self) -> None:
        self._snapshot = self._state_machine.snapshot()
        if self._turn_tracker.turn_number != self._snapshot.turn_number:
            self._turn_tracker.reset(turn_number=self._snapshot.turn_number)

    def _auto_advance(self) -> None:
        while True:
            if self._snapshot.phase == Phase.ATTACK:
                self._resolve_attack()
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
            "state_hash": self.state_hash(),
        }

    def _build_info(self, done: bool) -> Dict[str, object]:
        info = {
            "prizes": {player.name: progress.prizes_taken for player, progress in self._progress.items()},
            "damage": {player.name: self._damage_counters[player] for player in PlayerSide},
            "state_hash": self.state_hash(),
        }
        if done and self._winner is not None:
            info["winner"] = self._winner.name
        return info

    def _resolve_attack(self) -> None:
        attacker = self._snapshot.active_player
        defender = attacker.opponent()

        self._damage_counters[defender] += self._reward_config.damage_per_attack
        self._push_reward(attacker, self._reward_config.damage_reward)

        if self._damage_counters[defender] >= self._reward_config.damage_to_knockout:
            self._damage_counters[defender] = 0
            self._handle_knockout(attacker)

    def _handle_knockout(self, attacker: PlayerSide) -> None:
        progress = self._progress[attacker]
        progress.knockouts += 1
        progress.prizes_taken += 1
        self._push_reward(attacker, self._reward_config.prize_reward)

        if progress.prizes_taken >= self._reward_config.prizes_to_win:
            self._declare_winner(attacker)

    def _declare_winner(self, player: PlayerSide) -> None:
        if self._winner is not None:
            return
        self._winner = player
        self._state_machine.mark_game_over()
        self._push_reward(player, self._reward_config.win_reward)

    def _push_reward(self, player: PlayerSide, amount: float) -> None:
        if player is PlayerSide.PLAYER_ONE:
            self._pending_reward += amount
        else:
            self._pending_reward -= amount

    def _consume_pending_reward(self) -> float:
        reward = self._pending_reward
        self._pending_reward = 0.0
        return reward

    def state_hash(self) -> str:
        """Return a deterministic hash for the current environment state."""

        payload = {
            "snapshot": {
                "phase": self._snapshot.phase.name,
                "turn": self._snapshot.turn_number,
                "active_player": self._snapshot.active_player.name,
            },
            "turn_tracker": {
                "turn_number": self._turn_tracker.turn_number,
                "usage": {
                    action.name: count
                    for action, count in sorted(
                        self._turn_tracker.usage.items(), key=lambda item: item[0].name
                    )
                },
            },
            "progress": {
                player.name: asdict(progress)
                for player, progress in sorted(self._progress.items(), key=lambda item: item[0].name)
            },
            "damage": {player.name: self._damage_counters[player] for player in PlayerSide},
            "pending_reward": self._pending_reward,
            "winner": self._winner.name if self._winner is not None else None,
            "rng_state": self._rng.bit_generator.state,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf8")).hexdigest()


__all__ = [
    "ActionRulebook",
    "ActionSpec",
    "BattleEnv",
    "PlayerProgress",
    "RewardConfig",
    "TurnTracker",
]
