
from core.logging_config import setup_logging
from env.simple_env import SimpleEnv
from agents.random_agent import RandomAgent

def main():
    logger = setup_logging()
    env = SimpleEnv(seed=42)
    agent = RandomAgent()

    obs = env.reset()
    logger.info("Env reset: %s", obs)

    while True:
        action = agent.act(obs)
        result = env.step(action)
        logger.info("Turn=%s reward=%s done=%s", result.state["turn"], result.reward, result.done)
        if result.done:
            break
        obs = result.state

if __name__ == "__main__":
    main()
