
# PTCG AI Starter

最小可运行的项目脚手架，包含：
- Python 模块结构：`core/`, `env/`, `agents/`, `tests/`
- Poetry 项目管理
- pytest + pytest-cov（覆盖率）
- 统一 logging 配置

## 快速开始（Poetry 推荐）

```bash
# 1) 安装 poetry（若尚未安装）
# Linux/macOS
curl -sSL https://install.python-poetry.org | python3 -

# Windows (PowerShell)
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | py -

# 2) 切换到 Python 项目目录
cd rule

# 3) 安装依赖
poetry install

# 4) 运行测试（带覆盖率）
poetry run pytest -q --cov

# 5) 运行示例脚本
poetry run python scripts/example_run.py
```

## 自动卡牌规则流水线

### 人工审阅功能如何测试？

项目已经包含针对人工审阅流程的单元测试，运行以下命令即可验证 `Storage.mark_rule_reviewed` 的行为：

```bash
cd rule
poetry run pytest tests/test_auto_ir_pipeline.py -k mark_rule_reviewed -q
```

测试会在内置的 PostgreSQL 模拟连接上完成生成规则、提交审核以及审核通过/失败的完整流程。

### 卡牌信息与 IR 调试脚本

`rule/scripts/card_ir_demo.py` 脚本可以从标准输入或命令行参数中接收多行形如 `Pidgey MEW 16` 的卡牌信息，并展示从 PokemonTCG.io 获取到的原始数据以及经由 LLM 模板生成的 IR：

```bash
cd rule
poetry run python scripts/card_ir_demo.py <<'EOF'
Pidgey MEW 16
EOF
```

脚本默认使用 `postgresql://localhost:5432/pokemon` 连接串将原始卡牌数据与 IR 存入 PostgreSQL， 可以通过 `--database` 覆盖，或使用 `--api-key` 传入 PokemonTCG.io 的密钥。
