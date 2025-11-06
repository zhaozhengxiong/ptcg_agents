import pytest

from env.battle_env import BattleEnv


def test_first_attack_grants_damage_reward() -> None:
    env = BattleEnv()
    env.reset()

    result = env.step({"action_type": "DECLARE_ATTACK"})

    assert result.reward == pytest.approx(0.1)
    assert not result.done
    assert result.info["damage"]["PLAYER_TWO"] == 30


def test_knockout_awards_prize_reward() -> None:
    env = BattleEnv()
    env.reset()

    first = env.step({"action_type": "DECLARE_ATTACK"})
    assert first.reward == pytest.approx(0.1)

    second = env.step({"action_type": "DECLARE_ATTACK"})
    assert second.reward == pytest.approx(-0.1)

    third = env.step({"action_type": "DECLARE_ATTACK"})
    assert third.reward == pytest.approx(0.30000000000000004)
    assert third.info["prizes"]["PLAYER_ONE"] == 1
    assert third.info["damage"]["PLAYER_TWO"] == 0


def test_game_end_grants_final_reward() -> None:
    env = BattleEnv()
    env.reset()

    result = None
    while True:
        result = env.step({"action_type": "DECLARE_ATTACK"})
        if result.done:
            break

    assert result is not None
    assert result.done
    assert result.info["winner"] == "PLAYER_ONE"
    assert result.info["prizes"]["PLAYER_ONE"] == 6
    assert result.reward == pytest.approx(1.3)
