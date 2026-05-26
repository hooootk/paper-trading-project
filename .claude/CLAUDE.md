## 项目简介

双引擎纸面交易系统：LLM 多智能体流水线 + 24 因子规则回测引擎，基于 Python 3.12+，通过 Alpaca Paper Trading API 执行零风险模拟交易。

## 技术栈基线（不允许擅自升级）

- Python: ≥ 3.12，可使用 3.12+ 语法（PEP 695 type alias 等）
- 数据处理：numpy ≥ 1.26、pandas ≥ 2.2
- 数据源：yfinance ≥ 0.2.40（Yahoo Finance 市场数据）
- LLM：openai ≥ 1.30（Azure OpenAI GPT-4o，endpoint 通过环境变量配置）
- 配置管理：pydantic-settings ≥ 2.2（PAPER_TRADING_ 前缀）
- 交易执行：Alpaca Trading API（alpaca-py ≥ 0.30）
- 包管理：setuptools + pyproject.toml，pip install -e ".[dev]" 可编辑安装
- 代码检查：ruff ≥ 0.4（line-length=100）+ mypy ≥ 1.10（strict 模式）

## 快速导航

| 你想做什么 | 去哪里看 |
| --- | --- |
| 了解系统架构 | .harness/rules/architecture.md |
| 了解 LLM Agent 提示词 | src/paper_trading/agents/deciders.py |
| 了解 24 因子和回测逻辑 | src/paper_trading/backtest_engine.py |
| 了解 Alpaca 交易执行 | src/paper_trading/executor.py |
| 了解所有配置项 | src/paper_trading/config.py |
| 了解策略配置格式 | strategy_config.json |
| 了解环境变量模板 | .env.example |
| 了解 CLI 入口 | src/paper_trading/cli.py |
| 了解编码规范 | .claude/rules/testing.md |
| 运行全部测试 | tests/ |

## 硬性规则（必须遵守，CI 会验证）

1. 所有函数必须有类型注解，mypy strict 模式零容忍
2. API 密钥/密钥通过 `from paper_trading.config import settings` 获取，禁止硬编码
3. 禁止 `import *`，禁止可变默认参数
4. LLM 调用统一通过 `BaseAgent.call_llm()`，禁止绕开直接调用 OpenAI
5. 新增 LLM Agent 继承 `BaseAgent`，提示词模板放入 `agents/deciders.py`
6. 交易执行统一通过 `AlpacaExecutor`，禁止直接调用 Alpaca SDK
7. 新增因子或修改回测逻辑必须在 `strategy_config.json` 中可配置
8. 单文件 ≤ 400 行，单方法 ≤ 60 行

## 提交规范

- feat: 新功能
- fix: 修复
- refactor: 重构
- docs: 文档
- test: 测试
