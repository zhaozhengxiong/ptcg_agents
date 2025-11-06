
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

## Pokémon TCG 数据同步工具

项目内置了一个 `PokemonTCGSync` 工具，可通过 [pokemontcgsdk](https://github.com/PokemonTCG/pokemon-tcg-sdk-python) 把宝可梦卡牌、卡包等信息同步到 PostgreSQL。

### 准备工作

1. 保证 `rule/pyproject.toml` 中声明的依赖已经安装完毕：

   ```bash
   cd rule
   poetry install
   ```

2. 准备好 PostgreSQL，并创建好用于存储数据的数据库。

3. （可选）在 [pokemontcg.io](https://dev.pokemontcg.io/) 申请 API Key，提高接口速率与配额。

### 运行方式

工具提供了 CLI 脚本 `rule/scripts/sync_pokemon_tcg.py`，可以直接通过 Poetry 执行：

```bash
cd rule
poetry run python scripts/sync_pokemon_tcg.py \
  --database-url postgresql://username:password@host:5432/database_name \
  --api-key your_pokemontcg_io_key
```

命令行参数与环境变量说明：

| 参数 / 环境变量 | 说明 | 默认值 |
| --- | --- | --- |
| `--database-url` / `DATABASE_URL` | 连接 PostgreSQL 的 DSN，必填 | 无 |
| `--api-key` / `POKEMONTCG_IO_API_KEY` | pokemontcg.io 的 API Key，可为空 | 空字符串 |
| `--page-size` / `POKEMONTCG_SYNC_PAGE_SIZE` | 每次请求的卡牌数量 | `250` |
| `--max-card-pages` | 限制抓取的卡牌分页数，调试使用 | `None` |

工具会自动创建/更新以下数据表，并在每次执行时向 pokemontcgsdk 请求最新的数据进行 upsert：

- `pokemon_sets`
- `pokemon_cards`
- `pokemon_catalog_values`

执行成功后，即完成数据刷新，可在 PostgreSQL 中直接查询这些表获取最新的宝可梦卡牌信息。
