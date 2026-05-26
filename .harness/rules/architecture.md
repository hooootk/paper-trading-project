# 系统架构

## 概述

Paper Trading Project 是一个零风险的交易策略模拟平台，支持 LLM 多智能体交易和基于规则的因子回测。

## 系统设计

```
┌────────────────────────────────────────────────┐
│                  CLI 交互界面                   │
├────────────┬───────────────┬───────────────────┤
│  交易代理  │   回测引擎     │   执行器          │
├────────────┴───────────────┴───────────────────┤
│          LLM Agent 层（宏观/选股/风控）          │
├────────────────────────────────────────────────┤
│          数据层（yfinance + 技术指标）           │
├────────────────────────────────────────────────┤
│          配置层（pydantic-settings）            │
└────────────────────────────────────────────────┘
```

## 核心组件

- **CLI 界面**：交互式菜单（14 个功能）+ argparse 命令行参数
- **TradingAgent**：主编排器，连接所有组件，支持多策略并行交易
- **BacktestEngine**：24 因子规则回测引擎，含因子库、策略配置、绩效指标
- **AlpacaExecutor**：Alpaca Paper Trading API 封装，支持括号订单（止盈/止损）
- **LLM Agent 层**：宏观分析、个股分析、风险管理三个智能体协作决策
- **意图识别**：自然语言输入映射到菜单功能
- **配置层**：通过 pydantic-settings 管理所有环境变量

## 目录结构

```
paper-trading/
├── src/paper_trading/
│   ├── __init__.py
│   ├── main.py              # 入口：python -m paper_trading
│   ├── cli.py               # 交互式菜单 + argparse CLI
│   ├── config.py            # pydantic-settings 配置
│   ├── models.py            # Order / Position / Portfolio 数据模型
│   ├── trading_agent.py     # TradingAgent 主编排器
│   ├── backtest_engine.py   # 回测引擎（含 FactorLibrary、EvaluationMetrics、ReportGenerator）
│   ├── executor.py          # AlpacaExecutor — Alpaca API 封装
│   ├── intent.py            # 自然语言意图识别
│   ├── utils.py             # 工具函数
│   └── agents/
│       ├── base.py          # BaseAgent — LLM 调用基类
│       ├── data.py          # DataAgent — 市场数据获取 + 技术指标
│       ├── deciders.py      # 决策提示词模板（回测触发、调仓频率、意图识别）
│       ├── macro.py         # MacroAgent — 宏观市场阶段评估
│       ├── stock_analyst.py # StockAnalystAgent — 个股信号生成
│       └── risk_manager.py  # RiskManagerAgent — 组合风控评估
├── tests/
├── strategy_config.json     # 策略配置文件
├── pyproject.toml
└── .env.example
```

---

## 数据流：LLM 多智能体交易流水线

```
用户触发 (菜单 [1]/[2] 或 --live)
  │
  ▼
TradingAgent.run(target_date, dry_run)
  │
  ├─[1]─ DataAgent.fetch_market_data()
  │       下载 SPY + ^VIX + 自选股历史价格 (yfinance)
  │       返回 pd.DataFrame (列=tickers, 行=交易日)
  │
  ├─[2]─ MacroAgent.assess(hist, target_date)
  │       输入: SPY 5d/20d 收益, VIX 均值与趋势
  │       输出: {"market_phase": "Bull"|"Bear"|"Ranging"|"Panic",
  │               "risk_appetite": 0-10, "reasoning": "..."}
  │
  ├─[3]─ 对每只股票循环:
  │       StockAnalystAgent.analyze(ticker, tech_features, market_phase,
  │                                  risk_appetite, target_date, backtest_context)
  │       输入: 15 项技术指标 + 宏观状态 + 回测上下文
  │       输出: {"signal": "BUY"|"SELL"|"HOLD",
  │               "confidence": 0.0-1.0, "reasoning": "..."}
  │
  ├─[4]─ RiskManagerAgent.assess(hist, tickers, target_date, backtest_summary)
  │       输入: VaR(95%), VIX, 组合波动, 最大回撤, 回测绩效摘要
  │       输出: {"risk_level": "Low"|"Medium"|"High",
  │               "action": "Hold Normally"|"Reduce Overall Exposure"|
  │                         "Liquidate All Long Positions",
  │               "reasoning": "..."}
  │
  ├─[5]─ FrequencyDecider (通过 TradingAgent.decide_rebalance_frequency)
  │       输入: 市场阶段, VIX, SPY 波动率, 趋势强度
  │       输出: {"recommended_frequency": "daily"|"weekly"|"biweekly"|"monthly",
  │               "confidence": 0.0-1.0, "reasoning": "..."}
  │
  ├─[6]─ _compute_weights()
  │       将 BUY 信号的 confidence 映射为原始权重
  │       应用风控 action (Reduce → 权重×0.5, Liquidate → 全部清零)
  │       归一化为 target_weights dict
  │
  └─[7]─ AlpacaExecutor.rebalance(target_weights, dry_run)
          计算当前持仓 vs 目标权重差异
          提交买卖订单 (dry_run=True 时仅打印)
```

## 数据流：策略规则交易（无 LLM）

```
用户触发 (菜单 [3]/[4] 或 --use-strategy N)
  │
  ▼
TradingAgent.run_with_strategy(strategy_index, target_date, dry_run)
  │
  ├─[1]─ StrategyConfig.load() → 加载 strategy_config.json
  ├─[2]─ DataAgent.fetch_market_data() → 下载历史价格
  ├─[3]─ FactorLibrary.compute_all_factors() → 计算策略指定的因子
  ├─[4]─ _compute_strategy_signals()
  │       对每个因子: 应用阈值过滤 + 方向 × 权重
  │       加权求和 → 每只股票得到一个 composite score
  │       score > 0.2 → BUY, score < -0.2 → SELL, 否则 HOLD
  ├─[5]─ RiskManagerAgent.assess() → LLM 风控评估
  ├─[6]─ _strategy_weights() → composite score → 目标权重
  └─[7]─ AlpacaExecutor.rebalance()
```

## 数据流：回测引擎内部链路

```
BacktestEngine.run_one(strategy)
  │
  ├─[1]─ BacktestRunner(strategy)
  │       ├─ _fetch_data()        → yfinance 下载历史价格 + SPY
  │       ├─ _compute_signals()   → FactorLibrary 计算所有因子
  │       │                          weighted_sum 复合信号
  │       ├─ 主循环 (逐日):
  │       │   按 rebalance_interval 调仓
  │       │   _compute_target_weights(date_idx)
  │       │     → 根据 signal_logic + position_sizing 生成权重
  │       │   计算每日组合收益 → 记录交易日志
  │       └─ 返回 portfolio_returns (pd.Series)
  │
  ├─[2]─ EvaluationMetrics(returns, benchmark_returns)
  │       计算 13 项绩效指标
  │
  └─[3]─ ReportGenerator.print_report(strategy, metrics, trade_log)
          单策略报告 + 多策略对比表
```

## 数据流：多策略并行交易

```
用户触发 (菜单 [11])
  │
  ▼
TradingAgent.run_multi_strategies(indices, capital_weights, ...)
  │
  ├─[1]─ 加载并校验所有选中策略
  ├─[2]─ 合并所有策略的 ticker 集合 → 统一下载数据
  ├─[3]─ 对每个策略并行:
  │       ├─ _compute_strategy_signals()  → 各自计算因子信号
  │       └─ _strategy_weights()          → 各自生成目标权重
  ├─[4]─ 权重合并:
  │       combined[ticker] = Σ strategy_weight[ticker] × capital_weight[strategy]
  │       归一化 combined → 最终目标权重
  ├─[5]─ RiskManagerAgent.assess()  → 统一风控
  └─[6]─ AlpacaExecutor.rebalance(combined_weights)
```

## 关键数据结构

| 结构 | 类型 | 流向 |
|---|---|---|
| `market_state` | `{"market_phase": str, "risk_appetite": int, "reasoning": str}` | MacroAgent → TradingAgent → StockAnalyst / RiskManager |
| `stock_signals[ticker]` | `{"signal": "BUY"|"SELL"|"HOLD", "confidence": float, "reasoning": str}` | StockAnalystAgent → TradingAgent → _compute_weights |
| `risk_assessment` | `{"risk_level": "Low"|"Medium"|"High", "action": str, "reasoning": str}` | RiskManagerAgent → TradingAgent → _compute_weights |
| `target_weights` | `{ticker: float}` (总和=1.0) | TradingAgent → AlpacaExecutor.rebalance |
| `backtest_results[i]` | `{"name": str, "metrics": dict, "trade_log": list}` | BacktestEngine → TradingAgent |
| `frequency_decision` | `{"recommended_frequency": str, "confidence": float, "reasoning": str}` | FrequencyDecider → TradingAgent.report |

## TradingAgent 状态管理

`TradingAgent` 实例在单次会话中保持以下状态：

| 属性 | 类型 | 生命周期 |
|---|---|---|
| `tickers` | `list[str]` | 初始化设定，`run_with_strategy` 可覆盖 |
| `raw_data` | `pd.DataFrame` | 每次 `run()` / `run_with_strategy()` 刷新 |
| `market_state` | `dict` | 每次 `run()` 刷新 |
| `stock_signals` | `dict` | 每次 `run()` 刷新 |
| `risk_assessment` | `dict` | 每次 `run()` 刷新 |
| `target_weights` | `dict` | 每次 `run()` 刷新 |
| `backtest_results` | `list[dict]` | `trigger_backtest()` 追加 |
| `last_backtest_date` | `str` | `trigger_backtest()` 更新 |
| `strategy_mode` | `bool` | `run_with_strategy()` 设为 True |

同一个 `TradingAgent` 实例的回测结果会累积，供后续的 RiskManager 和 StockAnalyst 使用。
