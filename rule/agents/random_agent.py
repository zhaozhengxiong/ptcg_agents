
from typing import Dict, Any

class RandomAgent:
    """示例 Agent：返回一个空动作。实战中应输出结构化 JSON 动作。"""
    def act(self, observation: Dict[str, Any]) -> Dict[str, Any]:
        return {}
