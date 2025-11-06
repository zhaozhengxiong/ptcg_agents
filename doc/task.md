# 🧩 PTCG 多智能体策略分析与对战系统 — 任务拆解表

## **Phase 1：核心规则环境搭建（基础架构层）**

**目标：** 构建最小可运行的游戏环境（可手动输入动作完成一局游戏）

### 🧱 任务清单

1. **项目初始化**

   * 建立 Python 模块结构（`core/`, `env/`, `agents/`, `tests/`）
   * 配置 Poetry / pipenv / venv 环境
   * 集成 pytest + coverage + logging 基础设施

2. **对战状态机（State Machine）**

   * 设计枚举类：`Phase`, `PlayerSide`, `ActionType`
   * 构建主循环流程：`Setup → TurnBegin → Draw → MainPhase → Attack → EndTurn → GameEnd`
   * 定义状态切换条件与回合控制逻辑

3. **卡组与场景数据结构**

   * 定义 `Card`, `Deck`, `Zone`（手牌、牌堆、弃牌、奖赏、板凳等）
   * 建立唯一 `card_uid` 分配与追踪机制
   * 支持 JSON 载入卡组结构，支持Limitless卡组中"Copy to Clipboard"方式导出的卡组数据

4. **动作掩码系统（Legal Action Mask）**

   * 生成合法动作列表（PlayCard, AttachEnergy, Attack…）
   * 校验动作合法性，返回 `ERR_ILLEGAL_ACTION`
   * 提供 `env.legal_actions()` 接口

5. **奖励与胜负系统**

   * 设计奖励规则：胜利 +1、失败 −1、中间奖励（奖赏牌、击倒）
   * 实现 `env.step(action)` 的奖励输出

6. **随机性与复现控制**

   * 全局 RNG Seed 控制（numpy/random）
   * 状态哈希机制（状态一致性校验）

7. **基础测试**

   * 单元测试：状态切换、抽牌、攻击合法性
   * 集成测试：完整一局 Demo 对战（无复杂技能）

---

## **Phase 2：规则 IR / DSL 引擎（规则系统层）**

**目标：** 构建卡牌效果解释层，使 10–20 张卡可通过 IR 规则运行。

### ⚙️ 任务清单

1. **IR JSON Schema 设计**

   * 定义结构：`Trigger` / `Effect` / `Modifier`
   * 约定原子效果关键字（如 `Draw`, `SearchDeck`, `AddDamage` 等）

2. **原子效果函数库实现**

   * 每种原子效果实现对应 `Handler`
   * 统一接口：`apply_effect(effect, context)`

3. **IR 执行引擎**

   * 支持效果链执行（sequence）
   * 条件触发与 OncePerTurn 限制
   * 效果嵌套（Gate / Modifier）

4. **规则验证与异常处理**

   * 静态检查：非法字段、参数类型
   * 动态检查：越权动作、无目标错误

5. **IR 数据加载与缓存**

   * 支持从 PostgreSQL / JSON 文件读取 IR
   * 规则版本号校验

6. **单元测试自动化模板**

   * 针对每张卡生成正常/非法/边界测试

---

## **Phase 3：API 化与服务化（服务层）**

**目标：** 将裁判环境封装为 API，可供训练、前端或外部调用。

### 🌐 任务清单

1. **NestJS 服务端项目初始化**

   * 模块：`EnvModule`, `ReplayModule`, `LogModule`
   * TypeORM + PostgreSQL 连接

2. **Python 环境封装**

   * 通过 gRPC / REST 连接 Python 对战环境
   * 关键接口：

     * `POST /env/create`
     * `POST /env/step`
     * `GET /env/legal_actions`
     * `GET /env/replay`

3. **Replay 机制**

   * 保存 seed、规则版本、动作序列、状态哈希
   * `/replay/load`、`/replay/step`、`/replay/render`

4. **日志与错误追踪**

   * 统一错误码定义（`ERR_ILLEGAL_ACTION`、`ERR_TIMEOUT`）
   * 统一日志格式与回放追踪ID

---

## **Phase 4：Player Agent（智能体层）**

**目标：** 让系统实现可自主决策的智能体。

### 🧠 任务清单

1. **Action Schema 定义**

   * 标准化 JSON 格式动作描述（PlayCard/Attack/...）

2. **随机/脚本型 Bot**

   * 实现 RandomAgent / RuleBasedAgent（用于基准测试）

3. **强化学习 Agent**

   * 使用 PPO 或 IS-MCTS 实现基础智能体
   * 状态向量化（Observation Encoder）
   * 训练与评估脚本（Elo 曲线）

4. **对手池机制**

   * 保存历史策略模型
   * 随机抽取旧版本进行对战

5. **自博弈训练管线**

   * 多线程对战模拟（≥500步/秒）
   * 定期评估胜率 / 学习稳定性

---

## **Phase 5：前端可视化（展示层）**

**目标：** 可视化展示回放、训练日志与卡牌浏览。

### 🖥️ 任务清单

1. **React 前端项目初始化**

   * 组件结构：`ReplayViewer`, `CardBrowser`, `Dashboard`
   * Tailwind + Recharts 集成

2. **对局回放页面**

   * 展示玩家手牌、场地、行动动画
   * 可手动控制 `step/replay`

3. **训练可视化**

   * 绘制 Elo 曲线 / Reward 曲线
   * 训练日志查看器（WebSocket 实时更新）

4. **卡牌浏览器**

   * 展示 IR 内容 / 卡面图片
   * 支持过滤搜索

---

## **Phase 6：自动规则编译器（数据自动化层）**

**目标：** 利用 LLM 自动解析卡牌规则文本 → 生成 IR。

### 🧩 任务清单

1. **规则解析模板**

   * LLM 模板匹配：触发条件、效果槽位提取
   * 类型匹配校验（EffectType vs 参数）

2. **IR 生成与验证**

   * 自动生成 JSON IR
   * 自动执行单测模板验证

3. **人工审阅与版本冻结**

   * 生成规则版本 hash
   * 审阅后入库（PostgreSQL）

4. **流水线集成**

   * 卡牌文本 → IR → 单测 → 审核 → 部署

---

## ✅ 最终成果（系统闭环）

完成全部阶段后，系统具备：

* 自动化规则引擎
* 可复现对局环境
* 自主学习智能体
* Web 回放与分析
* 自动规则更新与测试流水线

