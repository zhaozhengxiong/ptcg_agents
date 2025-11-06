"""Battle state machine definitions for the Pokémon TCG environment.

This module contains the enumerations that describe the high level battle
phases, the player sides taking part in a duel and the actions that a player is
allowed to perform.  It also implements a small but fully deterministic state
machine that coordinates the turn flow described in the Phase 1 requirements.

The implementation focuses on the basic turn order only and does not yet model
card interactions.  Nevertheless, it provides a single place that other
components can query to understand the current phase, allowed actions and to
advance the duel.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, Sequence, Set


class Phase(Enum):
    """Enumeration of the high level battle phases.

    The order of the items mirrors the minimal loop required for Phase 1 of the
    project.  Additional phases can be introduced later without changing the
    public interface of the state machine.
    """

    SETUP = auto()
    TURN_BEGIN = auto()
    DRAW = auto()
    MAIN_PHASE = auto()
    ATTACK = auto()
    END_TURN = auto()
    GAME_END = auto()


class PlayerSide(Enum):
    """Two player sides that alternate control of the turn."""

    PLAYER_ONE = auto()
    PLAYER_TWO = auto()

    def opponent(self) -> "PlayerSide":
        return PlayerSide.PLAYER_TWO if self is PlayerSide.PLAYER_ONE else PlayerSide.PLAYER_ONE


class ActionType(Enum):
    """High level actions supported by the state machine.

    The list is intentionally broader than the transitions handled at the
    moment.  Actions such as ``PLAY_CARD`` or ``ATTACH_ENERGY`` keep the state in
    ``Phase.MAIN_PHASE`` but are included so that downstream code can build
    validation layers on top of the same enumeration.
    """

    PLAY_CARD = auto()
    ATTACH_ENERGY = auto()
    USE_ABILITY = auto()
    RETREAT = auto()
    DECLARE_ATTACK = auto()
    END_TURN = auto()
    PASS = auto()


@dataclass
class StateSnapshot:
    """Lightweight snapshot of the state machine.

    This helper is mostly used in tests and gives downstream code a
    serialisation friendly view of the current battle state.
    """

    phase: Phase
    active_player: PlayerSide
    turn_number: int
    legal_actions: Sequence[ActionType] = field(default_factory=list)


class BattleStateMachine:
    """Implements the core turn order described in the requirements."""

    #: Mapping between phases and actions that can be requested from a player.
    _LEGAL_ACTIONS: dict[Phase, Sequence[ActionType]] = {
        Phase.SETUP: (),
        Phase.TURN_BEGIN: (),
        Phase.DRAW: (),
        Phase.MAIN_PHASE: (
            ActionType.PLAY_CARD,
            ActionType.ATTACH_ENERGY,
            ActionType.USE_ABILITY,
            ActionType.RETREAT,
            ActionType.DECLARE_ATTACK,
            ActionType.END_TURN,
            ActionType.PASS,
        ),
        Phase.ATTACK: (),
        Phase.END_TURN: (),
        Phase.GAME_END: (),
    }

    def __init__(self) -> None:
        self._phase: Phase = Phase.SETUP
        self._active_player: PlayerSide = PlayerSide.PLAYER_ONE
        self._turn_number: int = 0
        self._game_over_pending: bool = False

    @property
    def phase(self) -> Phase:
        return self._phase

    @property
    def active_player(self) -> PlayerSide:
        return self._active_player

    @property
    def turn_number(self) -> int:
        return self._turn_number

    def legal_actions(self) -> Sequence[ActionType]:
        return self._LEGAL_ACTIONS.get(self._phase, ())

    def snapshot(self) -> StateSnapshot:
        return StateSnapshot(
            phase=self._phase,
            active_player=self._active_player,
            turn_number=self._turn_number,
            legal_actions=list(self.legal_actions()),
        )

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------
    def reset(self) -> None:
        """Return the machine to the initial setup phase."""

        self._phase = Phase.SETUP
        self._active_player = PlayerSide.PLAYER_ONE
        self._turn_number = 0
        self._game_over_pending = False

    def mark_game_over(self) -> None:
        """Request the machine to transition to ``Phase.GAME_END``.

        The transition is performed when the next transition out of ``ATTACK`` or
        ``END_TURN`` is processed.  This mirrors the real world flow where a KO
        is confirmed after attack damage is processed and end-of-turn checks are
        completed.
        """

        self._game_over_pending = True

    def advance(self, action: Optional[ActionType] = None) -> Phase:
        """Advance the state machine.

        Parameters
        ----------
        action:
            Optional action executed by the active player.  Only actions that
            change the phase are interpreted; all other actions simply keep the
            machine inside the current phase.

        Returns
        -------
        Phase
            The current phase after the transition has been processed.
        """

        handler = getattr(self, f"_handle_{self._phase.name.lower()}")
        handler(action)
        return self._phase

    # Individual phase handlers ------------------------------------------------
    def _handle_setup(self, action: Optional[ActionType]) -> None:  # noqa: D401 - short handlers
        del action
        self._phase = Phase.TURN_BEGIN
        self._turn_number = 1

    def _handle_turn_begin(self, action: Optional[ActionType]) -> None:
        del action
        self._phase = Phase.DRAW

    def _handle_draw(self, action: Optional[ActionType]) -> None:
        del action
        self._phase = Phase.MAIN_PHASE

    def _handle_main_phase(self, action: Optional[ActionType]) -> None:
        if action is None:
            return
        if action == ActionType.DECLARE_ATTACK:
            self._phase = Phase.ATTACK
        elif action == ActionType.END_TURN:
            self._phase = Phase.END_TURN
        elif action not in self._LEGAL_ACTIONS[Phase.MAIN_PHASE]:
            raise ValueError(f"Action {action!r} is not legal during the main phase")
        # Other actions (play card, attach energy, etc.) keep the machine in the
        # main phase.

    def _handle_attack(self, action: Optional[ActionType]) -> None:
        if action is not None:
            raise ValueError("Actions cannot be taken while the attack phase resolves")
        if self._game_over_pending:
            self._phase = Phase.GAME_END
        else:
            self._phase = Phase.END_TURN

    def _handle_end_turn(self, action: Optional[ActionType]) -> None:
        if action is not None:
            raise ValueError("Actions cannot be taken during the end turn checks")
        if self._game_over_pending:
            self._phase = Phase.GAME_END
        else:
            self._active_player = self._active_player.opponent()
            self._turn_number += 1
            self._phase = Phase.TURN_BEGIN

    def _handle_game_end(self, action: Optional[ActionType]) -> None:
        if action is not None:
            raise ValueError("No actions allowed after the game has ended")
        # Once the game is over the machine remains in GAME_END until reset.


__all__ = [
    "ActionType",
    "BattleStateMachine",
    "Phase",
    "PlayerSide",
    "StateSnapshot",
]
