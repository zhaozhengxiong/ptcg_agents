import os
from dotenv import load_dotenv
load_dotenv()

from openai import OpenAI
# —— Agents SDK （与你上一条消息的代码风格一致）——
# 这里假设 openai-agents-python 暴露以下 API：
from agents import Agent, Runtime, Message

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

runtime = Runtime(client=client, model="gpt-4o")

# —— 业务工具举例（自定义函数）——
def search_orders(keyword: str) -> list[str]:
    return [f"Order#{i}-{keyword}" for i in range(3)]

# —— 定义三个 Agent —— 
planner = Agent(
    name="planner",
    instructions=(
        "你是总策划。分解用户目标，决定应调用的专家Agent或工具；"
        "当结果足够时结束。"
    ),
)

researcher = Agent(
    name="researcher",
    instructions="你擅长检索与整合资料，给出简洁要点。",
)

ops = Agent(
    name="ops",
    instructions="你负责业务执行，调用搜索订单等内部函数并产出清单。",
    tools=[search_orders],   # 绑定自定义函数工具
)

# 让 planner 可以把其他 Agent 当“工具”调用（agents-as-tools）
planner.tools += [researcher.as_tool(), ops.as_tool()]

if __name__ == "__main__":
    task = "帮我找出近一个月热销的产品关键词：'手机壳'，并生成一份备货清单。"
    result = runtime.run(
        agent=planner,
        messages=[Message.from_user(task)],
        max_turns=8
    )
    print("\n=== 输出 ===\n")
    print(result.output_text)
