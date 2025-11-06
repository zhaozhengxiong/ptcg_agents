from core.random_control import seed_everything
from env.battle_env import BattleEnv


def test_state_hash_is_deterministic() -> None:
    seed_everything(2024)
    env = BattleEnv(seed=99)

    initial_obs = env.reset()
    initial_hash = initial_obs["state_hash"]

    env.step({"action_type": "DECLARE_ATTACK"})
    assert env.state_hash() != initial_hash

    env.reset()
    reset_hash = env.state_hash()
    assert reset_hash == initial_hash


def test_state_hash_exposed_in_step_result() -> None:
    env = BattleEnv(seed=11)
    env.reset()
    result = env.step({"action_type": "END_TURN"})
    assert "state_hash" in result.state
    assert "state_hash" in result.info
