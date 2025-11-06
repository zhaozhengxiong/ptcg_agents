
from env.simple_env import SimpleEnv

def test_env_runs_three_steps():
    env = SimpleEnv(seed=1)
    obs = env.reset()
    assert obs["turn"] == 0
    steps = 0
    done = False
    while not done:
        res = env.step({})
        steps += 1
        done = res.done
    assert steps == 3
