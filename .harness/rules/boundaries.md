# 模块边界与依赖规则

## 概述

本项目采用分层架构，各层之间有明确的依赖方向和调用约束。违反边界规则会导致循环依赖、测试困难和 LLM/Api 调用绕开统一入口等风险。

## 分层依赖图

```
┌─────────────────────────────────────────┐
│  CLI / 入口层                            │
│  cli.py, main.py                        │
│  可以依赖: 所有下层                       │
├─────────────────────────────────────────┤
│  编排层                                  │
│  trading_agent.py                       │
│  可以依赖: Agent 层, 回测引擎, 执行器     │
├──────────────┬──────────────────────────┤
│  Agent 层    │  回测引擎                  │
│  agents/     │  backtest_engine.py       │
│  可以依赖:   │  可以依赖: 数据层           │
│  配置层      │                           │
├──────────────┴──────────────────────────┤
│  执行器层                                │
│  executor.py                            │
│  可以依赖: 配置层, 数据层                 │
├─────────────────────────────────────────┤
│  数据层                                  │
│  agents/data.py, models.py, utils.py    │
│  可以依赖: 配置层                         │
├─────────────────────────────────────────┤
│  配置层                                  │
│  config.py                              │
│  不依赖任何业务模块                       │
└─────────────────────────────────────────┘
```

## 硬性边界规则

### 1. LLM 调用边界

| 允许 | 禁止 |
|---|---|
| 通过 `BaseAgent.call_llm()` 调用 LLM | 直接 `from openai import AzureOpenAI` 并调用 |
| 新增 Agent 继承 `BaseAgent` | 在 Agent 层之外构造 LLM 请求 |
| 提示词模板放入 `agents/deciders.py` | 提示词硬编码在业务逻辑中 |

**原因**：统一重试策略、限流处理、日志追踪、密钥管理。

### 2. 交易执行边界

| 允许 | 禁止 |
|---|---|
| 通过 `AlpacaExecutor` 提交订单 | 直接调用 `alpaca-py` SDK |
| `AlpacaExecutor.rebalance()` 统一调仓 | 在 CLI/TradingAgent 中自行构造订单 |

**原因**：统一 Dry Run 模式、买入力校验、括号订单管理。

### 3. 配置访问边界

| 允许 | 禁止 |
|---|---|
| `from paper_trading.config import settings` | 硬编码 API 密钥/端点 |
| 环境变量 `PAPER_TRADING_*` 或 `.env` 文件 | 在代码中写死默认敏感值 |

### 4. 数据获取边界

| 允许 | 禁止 |
|---|---|
| `DataAgent.fetch_market_data()` 获取行情 | 各模块自行 `yf.download()` 重复下载 |
| `DataAgent.technical_features()` 计算指标 | 在 Agent 层自行计算技术指标 |

### 5. 回测引擎边界

| 允许 | 禁止 |
|---|---|
| 通过 `BacktestEngine` 运行回测 | CLI/TradingAgent 自行组装回测循环 |
| 新增因子通过 `FactorLibrary` 方法 | 在回测循环中内联因子计算 |
| 策略配置存入 `strategy_config.json` | 策略参数硬编码在回测逻辑中 |

## Agent 接口契约

### MacroAgent

```
输入: pd.DataFrame (含 SPY, ^VIX 列), target_date: str
输出: {"market_phase": "Bull"|"Bear"|"Ranging"|"Panic",
       "risk_appetite": int(0-10),
       "reasoning": str}
降级: market_phase="Ranging", risk_appetite=5
```

### StockAnalystAgent

```
输入: ticker: str, tech_data: dict(15项指标), market_phase: str,
      risk_appetite: int, target_date: str, backtest_context: str
输出: {"signal": "BUY"|"SELL"|"HOLD",
       "confidence": float(0.0-1.0),
       "reasoning": str}
降级: signal="HOLD", confidence=0.0
```

### RiskManagerAgent

```
输入: data: pd.DataFrame, tickers: list[str], target_date: str,
      backtest_summary: str
输出: {"risk_level": "Low"|"Medium"|"High",
       "action": "Hold Normally"|"Reduce Overall Exposure"|"Liquidate All Long Positions",
       "reasoning": str}
降级: risk_level="Medium", action="Hold Normally"
```

### FrequencyDecider

```
输入: market_phase, risk_appetite, risk_level, vix_val, spy_vol, trend_strength
输出: {"recommended_frequency": "daily"|"weekly"|"biweekly"|"monthly",
       "confidence": float, "reasoning": str}
降级: 基于 VIX + market_phase 的启发式规则
```

### BacktestDecider

```
输入: market_phase, risk_appetite, risk_level, risk_action, vix_val, last_backtest
输出: {"should_backtest": bool, "urgency": "high"|"medium"|"low",
       "reasoning": str, "recommended_strategies": str}
降级: Panic/Bear → should_backtest=true, 其他 → false
```

## 模块依赖矩阵

| 模块 | 依赖 |
|---|---|
| `config.py` | (无) |
| `models.py` | pydantic |
| `utils.py` | (无) |
| `agents/base.py` | config |
| `agents/data.py` | config, base |
| `agents/deciders.py` | (纯字符串模板，无依赖) |
| `agents/macro.py` | base |
| `agents/stock_analyst.py` | base |
| `agents/risk_manager.py` | base |
| `backtest_engine.py` | numpy, pandas, yfinance |
| `executor.py` | config, yfinance |
| `trading_agent.py` | agents/*, backtest_engine, executor, config |
| `cli.py` | trading_agent, backtest_engine, executor, config, intent |
| `intent.py` | agents/base, agents/deciders |
| `main.py` | cli |

**关键约束**：`backtest_engine.py` 不依赖 Agent 层——回测是纯规则引擎，LLM-free。`executor.py` 不依赖 Agent 层——交易执行与信号来源解耦。
