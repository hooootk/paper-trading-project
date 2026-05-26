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

## 红线（不可违反）

1. **mypy strict 零容忍** — 所有函数必须有类型注解，CI 通过才允许合入
2. **禁止 `import *`，禁止可变默认参数** — ruff / mypy 会拦截
3. **单文件 ≤ 400 行，单方法 ≤ 60 行** — CI 自动检查
4. **新增因子/功能必须可配置化** — 新因子进 `strategy_config.json`，新参数进 `Settings` 类

## 快速导航

| 你想做什么 | 去哪里看 |
| --- | --- |
| 了解系统架构 | .harness/rules/architecture.md |
| 了解模块边界和依赖规则 | .harness/rules/boundaries.md |
| 了解编码规范 | .harness/rules/conventions.md |
| 了解需求与迭代计划 | .harness/changes/init.md |
| 了解 LLM Agent 接口规范 | .harness/rules/llm-agents.md |
| 了解 24 因子与策略配置 | .harness/rules/factors.md |
| 了解配置项与环境变量 | .harness/rules/config-reference.md |
| 了解测试规范 | .harness/rules/testing.md |


## 提交规范

- feat: 新功能
- fix: 修复
- refactor: 重构
- docs: 文档
- test: 测试
