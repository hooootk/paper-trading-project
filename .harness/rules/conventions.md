# 编码规范

## 概述

本文档汇总所有编码规范，包括代码风格、类型检查、CI 流程和提交约定。

## 代码风格

### 类型注解

- 所有函数必须有类型注解（mypy strict 模式零容忍）
- 使用 Python 3.12+ 语法（PEP 695 type alias 等）
- 参数和返回值类型必须显式声明

```python
# 正确
def compute_weights(signals: dict[str, float], max_positions: int = 10) -> dict[str, float]:
    ...

# 错误 — 缺少类型注解
def compute_weights(signals, max_positions=10):
    ...
```

### 导入规范

- 禁止 `import *`
- 禁止可变默认参数
- 导入顺序：标准库 → 第三方库 → 项目内部

### 命名约定

| 类型 | 风格 | 示例 |
|---|---|---|
| 模块/文件 | snake_case | `backtest_engine.py` |
| 类 | PascalCase | `TradingAgent`, `FactorLibrary` |
| 函数/方法 | snake_case | `fetch_market_data()` |
| 变量 | snake_case | `target_weights` |
| 常量 | UPPER_SNAKE | `FACTOR_POOL`, `RISK_FREE_RATE` |
| 私有方法 | _prefix | `_compute_weights()` |

### 文件与函数长度

- 单文件 ≤ 400 行
- 单方法 ≤ 60 行
- 超出时拆分为更小的模块或辅助方法

### 文档字符串

- 不要求 docstring，但复杂逻辑应有简短注释说明 WHY
- 公开 API 建议用一行注释描述用途

### 安全约束

- API 密钥/密钥通过 `from paper_trading.config import settings` 获取
- 禁止在任何文件中硬编码密钥、端点或敏感值
- 敏感字段不记录到日志

## 代码检查

### Ruff

```bash
ruff check .          # 代码风格检查
ruff format .         # 自动格式化
```

配置：`pyproject.toml` `[tool.ruff]`，line-length=100，target-version=py312，规则集 E/F/I/N/W/UP。

### Mypy

```bash
mypy src/             # 静态类型检查
```

配置：`pyproject.toml` `[tool.mypy]`，strict=true。

## CI/CD

配置文件：`.github/workflows/ci.yml`，触发条件：push 到 main/master/develop 或 PR 到 main/master。

| Job | 命令 | 说明 |
|---|---|---|
| Lint & Type Check | `ruff check .` + `mypy src/` | 代码风格 + 类型检查 |
| Test | `pytest --cov=paper_trading -v` | 测试 + 覆盖率 (Python 3.12 + 3.13) |
| File Size | `find src/ -name '*.py'` | 单文件行数 ≤ 400 |

**通过标准**：ruff 零告警、mypy 零错误、全部测试通过、无超行文件。

建议在提交前本地运行：

```bash
ruff check . && mypy src/ && pytest
```

## 提交规范

| 前缀 | 用途 |
|---|---|
| feat: | 新功能 |
| fix: | 修复 |
| refactor: | 重构 |
| docs: | 文档 |
| test: | 测试 |
| chore: | 构建/工具/依赖 |

示例：`feat: add trailing stop support to AlpacaExecutor`

## 技术栈基线（不允许擅自升级）

| 组件 | 版本要求 |
|---|---|
| Python | ≥ 3.12 |
| numpy | ≥ 1.26 |
| pandas | ≥ 2.2 |
| yfinance | ≥ 0.2.40 |
| openai | ≥ 1.30 |
| pydantic | ≥ 2.7 |
| pydantic-settings | ≥ 2.2 |
| alpaca-py | ≥ 0.30 |
| ruff | ≥ 0.4 |
| mypy | ≥ 1.10 |
| pytest | ≥ 8.2 |
