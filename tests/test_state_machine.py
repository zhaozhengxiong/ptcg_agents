from core.state_machine import (
    ActionType,
    BattleStateMachine,
    Phase,
    PlayerSide,
)


def _advance_to_main_phase(machine: BattleStateMachine) -> None:
    machine.advance()  # Setup -> TurnBegin
    machine.advance()  # TurnBegin -> Draw
    machine.advance()  # Draw -> MainPhase


def test_basic_turn_cycle_switches_player() -> None:
    machine = BattleStateMachine()

    _advance_to_main_phase(machine)
    assert machine.phase == Phase.MAIN_PHASE
    assert machine.active_player == PlayerSide.PLAYER_ONE
    assert machine.turn_number == 1

    machine.advance(ActionType.END_TURN)
    assert machine.phase == Phase.END_TURN

    machine.advance()  # EndTurn -> next player's turn begin
    assert machine.phase == Phase.TURN_BEGIN
    assert machine.active_player == PlayerSide.PLAYER_TWO
    assert machine.turn_number == 2


def test_attack_flow_transitions_to_end_turn() -> None:
    machine = BattleStateMachine()
    _advance_to_main_phase(machine)

    machine.advance(ActionType.DECLARE_ATTACK)
    assert machine.phase == Phase.ATTACK

    machine.advance()
    assert machine.phase == Phase.END_TURN


def test_game_end_is_triggered_when_marked() -> None:
    machine = BattleStateMachine()
    _advance_to_main_phase(machine)

    machine.advance(ActionType.DECLARE_ATTACK)
    machine.mark_game_over()

    machine.advance()
    assert machine.phase == Phase.GAME_END

