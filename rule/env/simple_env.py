
import random
from typing import Dict, Any, Optional

from env.types import StepResult

class SimpleEnv:
    """极简环境示例：随机产生奖励，便于 pipeline 验证。"""
    def __init__(self, seed: Optional[int] = None):
        self.rng = random.Random(seed)
        self.turn = 0
        self.done = False

    def reset(self) -> Dict[str, Any]:
        self.turn = 0
        self.done = False
        return {"turn": self.turn}

    def step(self, action: Optional[Dict[str, Any]] = None) -> StepResult:
        if self.done:
            return StepResult({"turn": self.turn}, 0.0, True, {"msg": "already done"})
        self.turn += 1
        reward = self.rng.choice([-1, 0, 1])
        self.done = self.turn >= 3
        return StepResult({"turn": self.turn}, float(reward), self.done, {})
