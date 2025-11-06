
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

# 2) 安装依赖
poetry install

# 3) 运行测试（带覆盖率）
poetry run pytest -q --cov

# 4) 运行示例脚本
poetry run python scripts/example_run.py
```
