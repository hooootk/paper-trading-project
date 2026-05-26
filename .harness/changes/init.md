# 纸面交易系统 — 初始需求分析

## 1. 项目定位

纸面交易系统是一款零风险的量化交易策略模拟与执行平台，面向量化交易研究者和个人投资者。用户可在 Alpaca Paper Trading 环境下进行策略研发、回测验证和模拟交易，无需承担真实资金风险。

## 2. 用户角色

| 角色 | 描述 | 核心需求 |
| --- | --- | --- |
| 策略研究者 | 通过因子组合构建量化策略并进行历史回测 | 策略配置、回测、绩效对比 |
| 交易执行者 | 利用 AI 或规则策略进行模拟交易 | 实盘模拟、订单管理、风控 |
| 系统开发者 | 扩展因子库、Agent 行为、交易接口 | 可扩展架构、类型安全 |

## 3. 功能需求

### 3.1 LLM 多智能体交易流水线

- **FR-LLM-01** 宏观分析 (MacroAgent)：基于 SPY 收益率和 VIX 指数，调用 LLM 判断当前市场阶段 (Bull/Bear/Ranging/Panic) 并输出风险偏好评分 (0-10)
- **FR-LLM-02** 个股信号生成 (StockAnalystAgent)：结合 15 项技术指标、市场环境和回测上下文，调用 LLM 为每只股票生成 BUY/SELL/HOLD 信号及置信度
- **FR-LLM-03** 组合风险管理 (RiskManagerAgent)：基于 VaR、最大回撤、VIX、组合波动率及回测结果，调用 LLM 输出风险等级与调仓建议
- **FR-LLM-04** 调仓频率决策 (FrequencyDecider)：基于市场阶段和 SPY 趋势强度，由 LLM 推荐 daily/weekly/biweekly/monthly 的最优调仓频率
- **FR-LLM-05** 回测触发决策 (BacktestDecider)：基于市场压力状态和距上次回测时间，由 LLM 判断是否需要触发策略回测
- **FR-LLM-06** 自然语言意图识别：用户输入中文或英文描述，LLM 自动映射到 14 个功能模块中的对应操作
- **FR-LLM-07** 权重计算：根据信号置信度生成目标持仓权重，支持风险降权（Reduce Exposure）和清仓（Liquidate All）覆盖

### 3.2 24 因子规则回测引擎

- **FR-BT-01** 因子库 (FactorLibrary)：涵盖 5 大类共 24 个技术因子
  - 趋势类：SMA 交叉 (20/50, 50/200)、EMA 交叉 (12/26)、ADX(14)
  - 动量类：RSI(14)、MACD 信号/直方图、20/60/120 日动量、Stochastic(14)、CCI(20)、Williams %R(14)
  - 波动类：布林带位置/挤压、20 日波动率、波动率状态、ATR(14)
  - 成交量类：量比、量价趋势、OBV 趋势
  - 风险/其他：Beta(SPY)、5 日反转、60 日回撤
- **FR-BT-02** 策略配置管理 (StrategyConfig)：支持 JSON 文件加载、验证、随机生成，策略包含因子选择、权重、方向、阈值、调仓频率、仓位管理等参数
- **FR-BT-03** 回测执行 (BacktestRunner)：Yahoo Finance 获取历史数据，按调仓间隔计算目标权重，生成每日组合收益率序列，记录完整交易日志
- **FR-BT-04** 绩效评估 (EvaluationMetrics)：计算 13 项指标 —— 总收益、年化收益、Sharpe/Sortino/Calmar 比率、最大回撤、年化波动、Beta、胜率、盈亏比、盈利因子、VaR(95%)、CVaR(95%)
- **FR-BT-05** 策略对比 (ReportGenerator)：单策略详细报告 + 多策略横向对比排名表

### 3.3 组合管理

- **FR-PM-01** 资金加权分配：多策略并行交易时支持等权重和自定义资金分配比例
- **FR-PM-02** 仓位规模管理：支持 equal_weight、factor_score、risk_parity 三种仓位计算方式，可配置最大持仓数
- **FR-PM-03** 自动最优策略选择：回测全部策略后按 6 项指标综合排名（Sharpe、Calmar、Sortino、Profit Factor、MaxDD、Win Rate），自动选择最优策略执行交易

### 3.4 交易执行

- **FR-TR-01** Alpaca Paper Trading 对接：通过 alpaca-py SDK 调用模拟交易接口，支持账户查询、持仓管理、市价订单提交
- **FR-TR-02** 组合再平衡 (Rebalance)：根据目标权重与实际持仓差异，自动计算买卖数量并提交订单
- **FR-TR-03** 括号订单 (Bracket Orders)：买入时自动附加止盈限价单和止损止损单，支持 OCO (One-Cancels-Other) 模式
- **FR-TR-04** TP/SL 管理：为已有持仓补充止盈止损订单，查询当前持仓盈亏是否触及 TP/SL 阈值
- **FR-TR-05** 资金限制：提交买入订单时校验买入力 (buying power)，超出时自动缩量

### 3.5 交互界面

- **FR-UI-01** 交互式菜单：14 个功能选项的 ASCII 菜单，支持序号选择
- **FR-UI-02** 命令行参数：支持 argparse 一键执行（--live, --backtest, --auto-select, --summary, --generate-config 等）
- **FR-UI-03** Dry Run 模式：所有实盘操作均有 dry_run 参数，默认不提交真实订单
- **FR-UI-04** 策略列表展示：显示全部可用策略的名称、标的、因子数、信号逻辑、仓位管理方式

### 3.6 配置管理

- **FR-CF-01** 环境变量驱动：所有配置通过 `PAPER_TRADING_` 前缀环境变量管理 (pydantic-settings)，支持 .env 文件
- **FR-CF-02** Azure OpenAI 集成：通过 endpoint + API key + deployment 配置 LLM 接入
- **FR-CF-03** 策略配置文件：strategy_config.json 存储全部策略定义，支持手动编辑和自动生成

## 4. 非功能需求

| 编号 | 类别 | 要求 |
| --- | --- | --- |
| NFR-01 | 语言 | Python 3.12+，可使用 PEP 695 等新语法 |
| NFR-02 | 类型安全 | mypy strict 模式零容忍，所有函数必须有类型注解 |
| NFR-03 | 代码风格 | ruff check 零告警 (line-length=100) |
| NFR-04 | 单文件限制 | ≤ 400 行，单方法 ≤ 60 行 |
| NFR-05 | 架构约束 | LLM 调用必须通过 BaseAgent.call_llm()，交易必须通过 AlpacaExecutor，禁止直接调用 OpenAI/alpaca-py |
| NFR-06 | 安全约束 | 禁止硬编码 API 密钥，统一通过 config.settings 获取 |
| NFR-07 | 数据源 | yfinance ≥ 0.2.40 获取市场数据 |
| NFR-08 | LLM 容错 | call_llm 内置指数退避重试 (最多 5 次)，LLM 不可用时降级为启发式规则 |
| NFR-09 | CI/CD | GitHub Actions 双 Job 并行 (lint + mypy / pytest matrix 3.12+3.13) |
| NFR-10 | 包管理 | setuptools + pyproject.toml，pip install -e ".[dev]" 可编辑安装 |

## 5. 数据模型

- **Order**: symbol, quantity, price, side (buy/sell)
- **Position**: symbol, quantity, average_price
- **Portfolio**: cash, positions[]
- **Settings**: 26 个配置字段 (pydantic BaseSettings)
- **StrategyConfig**: name, dates, tickers, factors, signal_logic, rebalance_frequency, position_sizing, max_positions

## 6. 外部依赖

| 服务 | 用途 | 备选/降级 |
| --- | --- | --- |
| Azure OpenAI (GPT-4o) | LLM Agent 推理、意图识别 | 启发式规则 fallback |
| Alpaca Paper Trading API | 模拟交易执行 | 标记为可选，无 SDK 时跳过 |
| Yahoo Finance (yfinance) | 历史行情 + 当前价格 | 无替代，数据缺失抛异常 |
