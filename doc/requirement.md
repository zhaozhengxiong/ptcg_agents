

# 🎯 项目名称

**PTCG 多智能体策略分析与对战系统**

---

## 一、总体目标

构建一个可扩展、可训练、可复现的 Pokémon TCG（PTCG）AI 系统。
系统应支持：

* ✅ 自动对战模拟（两方智能体对弈）
* ✅ 自主学习（强化学习 / 自博弈）
* ✅ 规则合规（环境裁判引擎）
* ✅ 新系列卡自动上线（通过 IR 数据驱动）
* ✅ 回放与可视化

---

## 二、系统组成与职责划分

| 模块                                   | 职责                                           | 技术栈                         |
| ------------------------------------ | -------------------------------------------- | --------------------------- |
| 🧠 **Player Agent**                  | 决策执行。输入观测与合法动作掩码，输出结构化动作（如PlayCard、Attack等）。 | Python + RL (PPO / IS-MCTS) |
| ⚖️ **Rules Environment Agent（裁判环境）** | 负责对战状态、合法性判定、效果结算、阶段推进、奖励输出。                 | Python + Gym API            |
| 🗃️ **Card Knowledge Base**          | 卡面数据、规则IR、原子效果定义、Handler注册表。                 | PostgreSQL / JSON           |
| 🏗️ **IR/DSL 编译器 Agent（离线工具）**       | 将牌文解析为结构化规则 IR，进行静态检查与单测生成。                  | Python + OpenAI Agents SDK  |
| 💾 **Replay & Logging**              | 保存完整对局数据（seed、动作、随机源、规则版本）以便回放与回归测试。         | PostgreSQL / 文件系统           |
| 🌐 **API 网关**                        | 供前端与训练端调用环境创建、step、legal_actions、replay等接口。  | NestJS (TypeScript)         |
| 🖥️ **前端可视化**                        | 回放UI、训练日志、卡牌浏览器、对战可视化。                       | React + Tailwind + Recharts |
| 🧩 **训练与评估模块**                       | 自博弈训练、对手池维护、Elo 曲线统计。                        | Python + RLlib / custom PPO |

---

## 三、功能需求

### 3.1 游戏规则环境（Environment）

* 支持完整对战流程：
  `Setup → TurnBegin → Draw → MainPhase → Attack → EndTurn → GameEnd`
* 对战流程各个阶段的解释：

| 阶段              | 说明                                     |
| --------------- | -------------------------------------- |
| **Setup**       | 双方建立初始场地（起手宝可梦、奖赏卡、洗牌）。                |
| **TurnBegin**   | 进入新回合，结算效果（如异常状态、场地效果等）。               |
| **Draw**        | 当前玩家抽一张牌。                 |
| **MainPhase** | 玩家可以打出卡、附能量、进化、使用能力、替换场上宝可梦等。 |
| **Attack**      | 进行攻击，计算伤害，结算效果。                        |
| **EndTurn**     | 回合结束，处理“回合结束时”的触发效果。                   |

* 管理随机性（统一 RNG Seed）
* 生成合法动作掩码（Mask）
* 执行卡牌效果（基于 IR / Handler）
* 提供奖励与观测（不完全信息）
* 回放可复现
* 阶段状态机控制各动作类型可执行时机（PlayCard、AttachEnergy等）

---

### 3.2 动作协议（Action Schema）

动作统一为结构化 JSON：

```json
{
  "action_type": "PlayCard|Attack|UseAbility|AttachEnergy|Evolve|Retreat|EndTurn",
  "payload": {
    "card_uid": "h_3",
    "targets": ["opp_active"],
    "cost_payment": [{"energy_uid": "e_5"}]
  }
}
```

* 环境负责验证动作合法性，否则返回 `ERR_ILLEGAL_ACTION`。
* 每回合提供合法动作列表或动作掩码。

---

### 3.3 卡牌规则系统（IR/DSL）

* **卡面IR定义**：基于JSON结构描述触发条件、效果序列、限制条件。
* **原子效果集**（v1共约15种）：

  * `Draw`, `SearchDeck`, `AttachEnergy`, `AddDamage`, `ModifyDamage`,
    `Discard`, `FlipCoins`, `ApplyCondition`, `Gate`, `OncePerTurn`,
    `Replacement`, `Reveal`, `Shuffle`, `MoveEnergy`, `KnockOut`.
* **DSL组合结构**：

  * `Trigger`：触发时机（OnPlay/OnEvolve/OnAttack/BetweenTurns）
  * `Effect`：原子指令序列 + 条件
  * `Modifier`：持续修饰效果
* **Handler机制**：仅对极少数复杂牌（如替代攻击、条件嵌套）使用 Python 代码实现。

---

### 3.4 规则编译器 Agent（离线）

* 解析牌文 → 结构化 IR
* 模板匹配 + LLM 槽位填充 + 类型检查
* 自动生成单测（正常/非法/边界）
* 人工审阅后入库并冻结版本号
* 产出内容：

  * IR 文件
  * 单测脚本
  * 规则版本 hash

---

### 3.5 观测与隐藏信息（Observation）

| 信息类型     | 自己可见  | 对手可见       |
| -------- | ----- | ---------- |
| 手牌       | ✅     | ❌          |
| 牌堆余量     | ✅     | ✅（仅数量）     |
| 弃牌区      | ✅     | ✅          |
| 奖赏牌      | ✅（数量） | ✅（数量）      |
| 主动宝可梦/板凳 | ✅     | ✅（但不含手牌信息） |
| 特殊状态     | ✅     | ✅          |
| 场地牌      | ✅     | ✅          |
| 标志/已使用能力 | ✅     | ✅          |

---

### 3.6 奖励设计

* 胜利 +1，失败 −1。
* 可选中间奖励（例如获得奖赏 +0.2，击倒对手 +0.3）。
* 自博弈与对手池结合以防止“刷分”策略。

---

### 3.7 API 接口定义（简版）

| 接口                   | 方法   | 功能               |
| -------------------- | ---- | ---------------- |
| `/env/create`        | POST | 创建新环境（传入牌组、seed） |
| `/env/step`          | POST | 执行动作并推进状态        |
| `/env/legal_actions` | GET  | 获取当前合法动作列表       |
| `/env/replay`        | GET  | 获取对局回放数据         |
| `/env/state`         | GET  | 获取当前状态快照         |

---

### 3.8 Replay 与可复现

* 保存 `seed`、规则版本号、动作序列、随机序列索引、状态哈希。
* 提供 `/replay/load`、`/replay/step`、`/replay/render`。
* 任意回放可重演，确保训练与线上对局一致。

---

## 四、非功能需求

| 类别       | 需求                         |
| -------- | -------------------------- |
| **可复现性** | 同一 seed 与动作序列必定生成相同结果      |
| **可扩展性** | 新系列卡牌仅需新增 IR 数据或少量 Handler |
| **性能**   | 每秒可模拟 ≥500 对局步（多线程批量Env）   |
| **安全性**  | Action 合法性验证 + 状态哈希同步机制    |
| **测试覆盖** | 单元测试（每张卡 ≥3条），集成测试（对战完整流程） |

---

## 五、开发分阶段计划

| 阶段                       | 内容                    | 产出        |
| ------------------------ | --------------------- | --------- |
| **Phase 1：核心环境**         | 状态机、动作掩码、基础攻击结算、奖赏系统  | 可对战demo   |
| **Phase 2：IR/DSL引擎**     | 原子效果库、规则解析、测试框架       | 10–20张卡运行 |
| **Phase 3：裁判服务API化**     | gRPC/REST接口、回放机制、日志系统 | 环境Server  |
| **Phase 4：Player Agent** | 脚本Bot → PPO / IS-MCTS | 自博弈训练     |
| **Phase 5：前端UI**         | React可视化回放界面          | 调试/展示工具   |
| **Phase 6：自动规则编译器**      | LLM模板解析 + IR校验        | 卡牌数据自动化流程 |

---

## 六、未来扩展方向

* 支持 **对战录像导入回放分析**。
* 引入 **AI解说 / 策略推荐** 模块。
* 通过 WebSocket 实现实时对战（人类 vs AI）。
* 多Agent协作分析卡组胜率、出牌策略、卡组构筑优化。

