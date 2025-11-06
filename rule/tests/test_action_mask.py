import pytest

from core.errors import IllegalActionError
from env.battle_env import BattleEnv


def _action_names(env: BattleEnv) -> set[str]:
    return {entry["action_type"] for entry in env.legal_actions()}


def test_environment_exposes_main_phase_actions() -> None:
    env = BattleEnv()
    observation = env.reset()

    assert observation["phase"] == "MAIN_PHASE"
    assert observation["turn"] == 1
    assert "state_hash" in observation

    legal_names = _action_names(env)
    assert {"PLAY_CARD", "ATTACH_ENERGY", "DECLARE_ATTACK", "END_TURN"}.issubset(legal_names)


def test_attach_energy_only_once_per_turn() -> None:
    env = BattleEnv()
    env.reset()

    env.step({"action_type": "ATTACH_ENERGY"})
    legal_names = _action_names(env)
    assert "ATTACH_ENERGY" not in legal_names

    with pytest.raises(IllegalActionError) as excinfo:
        env.step({"action_type": "ATTACH_ENERGY"})
    assert excinfo.value.code == "ERR_ILLEGAL_ACTION"


def test_end_turn_resets_action_limits() -> None:
    env = BattleEnv()
    env.reset()

    env.step({"action_type": "ATTACH_ENERGY"})
    env.step({"action_type": "END_TURN"})

    observation = env.legal_actions()
    legal_names = {entry["action_type"] for entry in observation}
    assert "ATTACH_ENERGY" in legal_names


def test_unknown_action_type_raises() -> None:
    env = BattleEnv()
    env.reset()

    with pytest.raises(IllegalActionError):
        env.step({"action_type": "FLY_AWAY"})


def test_attack_ends_turn_and_advances_state_machine() -> None:
    env = BattleEnv()
    env.reset()

    result = env.step({"action_type": "DECLARE_ATTACK"})
    observation = env.legal_actions()
    legal_names = {entry["action_type"] for entry in observation}
    assert "DECLARE_ATTACK" in legal_names

    # Ensure the state machine switched to the opposing player.
    assert result.state["turn"] == 2
    assert result.state["phase"] == "MAIN_PHASE"
    assert "state_hash" in result.state


def test_legal_action_payload_contains_metadata() -> None:
    env = BattleEnv()
    env.reset()
    entry = env.legal_actions()[0]
    assert {"action_type", "description", "phase", "constraints"}.issubset(entry)

