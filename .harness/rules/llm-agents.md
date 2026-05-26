# LLM Agent 设计文档

## 概述

系统包含 5 个 LLM Agent 和 1 个意图识别器，均继承 `BaseAgent`，通过 Azure OpenAI GPT-4o 执行推理。所有 Agent 共享统一的调用层、重试策略和降级机制。

## 架构

```
BaseAgent (agents/base.py)
  ├─ call_llm(prompt) → dict | None
  │    ├─ 调用 Azure OpenAI (GPT-4o, JSON mode)
  │    ├─ 指数退避重试 (最多 5 次)
  │    ├─ 429 限流自动等待
  │    └─ 全部失败返回 None
  │
  ├─ MacroAgent (agents/macro.py)
  ├─ StockAnalystAgent (agents/stock_analyst.py)
  ├─ RiskManagerAgent (agents/risk_manager.py)
  ├─ FrequencyDecider (trading_agent.py 内联)
  ├─ BacktestDecider (trading_agent.py 内联)
  └─ IntentRecognizer (intent.py)
```

## BaseAgent 调用机制

```
BaseAgent.call_llm(user_prompt, retries=5)
  │
  ├─ 构造请求:
  │   model = settings.azure_openai_deployment
  │   messages = [system_prompt, user_prompt]
  │   temperature = 0.1 (可覆盖)
  │   response_format = {"type": "json_object"}
  │
  ├─ 成功 → json.loads(response) → dict
  │
  └─ 失败:
      ├─ JSONDecodeError → 立即重试
      ├─ 429 (限流) → 等待 Retry-After + 3s 或 60s × 次数
      └─ 其他错误 → 指数退避 2^attempt × 5s
```

**统一约束**：
- 所有 Agent 调用必须通过 `BaseAgent.call_llm()`，禁止绕开直接调用 OpenAI
- `temperature = 0.1` 保证输出确定性
- 始终使用 `response_format = {"type": "json_object"}` 确保结构化输出

---

## Agent 1: MacroAgent（宏观分析）

| 项目 | 内容 |
|---|---|
| 文件 | `agents/macro.py` |
| 角色 | 宏观市场分析师 |
| 触发时机 | 每个 LLM 交易周期的第一步 |
| 提示词 | `MACRO_SYSTEM_PROMPT` + `MACRO_USER_TEMPLATE` |

**输入数据**：

| 字段 | 来源 | 说明 |
|---|---|---|
| target_date | 调用参数 | 当前交易日 |
| spy_5d | 计算 | SPY 近 5 日收益率 (%) |
| spy_20d | 计算 | SPY 近 20 日收益率 (%) |
| vix_val | 计算 | VIX 近 5 日均值 |
| vix_trend | 计算 | VIX 5 日变化 |

**输出 JSON Schema**：

```json
{
    "market_phase": "Bull | Bear | Ranging | Panic",
    "risk_appetite": "integer 0-10 (10 = 极度贪婪)",
    "reasoning": "string (一句话引用具体数据点)"
}
```

**判断逻辑**（提示词中定义）：
- Bull: 持续上涨 + VIX<20 + 正动量
- Bear: 持续下跌 + VIX>25 + 负动量
- Ranging: 横盘 + 中等 VIX
- Panic: 急跌 + VIX>35 + 极度恐慌

**Fallback**：
```python
{"market_phase": "Ranging", "risk_appetite": 5, "reasoning": "LLM unavailable"}
```

---

## Agent 2: StockAnalystAgent（个股分析）

| 项目 | 内容 |
|---|---|
| 文件 | `agents/stock_analyst.py` |
| 角色 | 量化分析师 |
| 触发时机 | 宏观评估后，对每只股票逐一调用（间隔 1.5s） |
| 提示词 | `STOCK_SYSTEM_PROMPT` + `STOCK_USER_TEMPLATE` |

**输入数据**：

| 字段 | 来源 | 说明 |
|---|---|---|
| ticker | 循环参数 | 股票代码 |
| tech_data | DataAgent.technical_features() | 15 项技术指标 |
| market_phase | MacroAgent 输出 | 当前市场阶段 |
| risk_appetite | MacroAgent 输出 | 风险偏好 0-10 |
| backtest_context | TradingAgent._build_backtest_context() | 该股票的历史回测表现 |

**输出 JSON Schema**：

```json
{
    "signal": "BUY | SELL | HOLD",
    "confidence": "float 0.0-1.0",
    "reasoning": "string (引用具体指标、宏观环境和回测结果)"
}
```

**交易规则**（提示词中定义）：

| 市场阶段 | 条件 | 信号 |
|---|---|---|
| Panic | 多类别因子强烈看多 | HOLD/SELL（默认保守） |
| Bull (appetite ≥ 7) | EMA12>EMA26 + MACD_hist>0 + Price>SMA20 + Stoch<80 | BUY |
| Bear | RSI<30 + DD_60d < -15% | BUY（抄底） |
| Ranging | bb_position < -0.8 | BUY（均值回复） |
| Ranging | bb_position > +0.8 | SELL（均值回复） |

**Fallback**：
```python
{"signal": "HOLD", "confidence": 0.0, "reasoning": "LLM unavailable"}
```

---

## Agent 3: RiskManagerAgent（风控评估）

| 项目 | 内容 |
|---|---|
| 文件 | `agents/risk_manager.py` |
| 角色 | 首席风控官 |
| 触发时机 | 所有个股信号生成完毕后 |
| 提示词 | `RISK_SYSTEM_PROMPT` + `RISK_USER_TEMPLATE` |

**输入数据**：

| 字段 | 来源 | 说明 |
|---|---|---|
| portfolio_holdings | 当前 tickers 列表 | 组合持仓 |
| max_dd | 计算 | SPY 252 日最大回撤 (%) |
| var_95 | 计算 | 等权组合 95% 1 日 VaR (%) |
| vix_val | 计算 | 当前 VIX |
| port_vol | 计算 | 等权组合 20 日年化波动 (%) |
| backtest_summary | TradingAgent._build_backtest_summary() | 所有策略回测绩效摘要 |

**输出 JSON Schema**：

```json
{
    "risk_level": "Low | Medium | High",
    "action": "Hold Normally | Reduce Overall Exposure | Liquidate All Long Positions",
    "reasoning": "string"
}
```

**决策阈值**（提示词中定义）：

| 条件 | action |
|---|---|
| VaR < -2% 或 MaxDD < -15% 或 VIX > 35 | Reduce 或 Liquidate |
| VIX > 40 或 MaxDD < -25% | Liquidate All |
| 回测 Sharpe < 0 且 MaxDD > 20% | 升级风险等级 |
| 回测 ProfitFactor < 1.0 | 建议 Reduce |
| 无回测数据 | 更保守对待敞口 |

**Fallback**：
```python
{"risk_level": "Medium", "action": "Hold Normally", "reasoning": "LLM unavailable"}
```

---

## Agent 4: FrequencyDecider（调仓频率决策）

| 项目 | 内容 |
|---|---|
| 文件 | `agents/deciders.py` + `trading_agent.py::decide_rebalance_frequency()` |
| 角色 | 组合再平衡策略师 |
| 触发时机 | 风控评估后 |
| 提示词 | `FREQUENCY_DECISION_TEMPLATE` |

**输入数据**：

| 字段 | 说明 |
|---|---|
| market_phase | 市场阶段 |
| risk_appetite | 风险偏好 0-10 |
| risk_level | 风控等级 |
| vix_val | 当前 VIX |
| spy_vol | SPY 20 日年化波动率 (%) |
| trend_strength | SPY 60 日趋势强度 (|ret|/vol) |

**输出 JSON Schema**：

```json
{
    "recommended_frequency": "daily | weekly | biweekly | monthly",
    "confidence": "float 0.0-1.0",
    "reasoning": "string"
}
```

**Fallback**（启发式规则）：

| VIX | 市场阶段 | 推荐频率 |
|---|---|---|
| > 35 或 Panic | — | daily |
| > 25 或 Bear | — | weekly |
| 15-25 | Ranging | biweekly |
| < 15 | Bull | monthly |

---

## Agent 5: BacktestDecider（回测触发决策）

| 项目 | 内容 |
|---|---|
| 文件 | `agents/deciders.py` + `trading_agent.py::decide_backtest()` |
| 角色 | 量化策略审计师 |
| 触发时机 | 用户选择自动回测模式（菜单 [7]） |
| 提示词 | `BACKTEST_DECISION_TEMPLATE` |

**输入数据**：

| 字段 | 说明 |
|---|---|
| market_phase | 市场阶段 |
| risk_appetite | 风险偏好 |
| risk_level | 风控等级 |
| risk_action | 风控建议 |
| vix_val | 当前 VIX |
| last_backtest | 上次回测日期或 "Never" |

**输出 JSON Schema**：

```json
{
    "should_backtest": "bool",
    "urgency": "high | medium | low",
    "reasoning": "string",
    "recommended_strategies": "string (如 '0,1,2' 或 'all')"
}
```

**Fallback**（启发式规则）：

- `Panic` 或 `Bear` → should_backtest = true
- VIX > 30 → should_backtest = true
- 其他 → should_backtest = false

---

## 意图识别 (IntentRecognizer)

| 项目 | 内容 |
|---|---|
| 文件 | `agents/deciders.py` + `intent.py` |
| 角色 | 意图分类器 |
| 触发时机 | 用户选择菜单 [14] 输入自然语言 |
| 提示词 | `INTENT_RECOGNITION_SYSTEM` + `INTENT_RECOGNITION_TEMPLATE` |

**输出 JSON Schema**：

```json
{
    "matched_options": "list[int] (1-13 的功能编号)",
    "confidence": "float 0.0-1.0",
    "reasoning": "string (中文解释匹配原因)"
}
```

**处理流程**：
1. 单匹配 + confidence ≥ 0.7 → Y/n 确认后执行
2. 单匹配 + confidence < 0.7 → y/N 确认后执行
3. 多匹配 → 用户手动选择
4. 无匹配 → 列出所有可用功能

**Fallback**：
```python
{"matched_options": [], "confidence": 0.0, "reasoning": "LLM unavailable --- cannot recognize intent."}
```

---

## 设计原则

1. **无状态** — Agent 不持有交易状态，所有上下文通过 prompt 参数传入
2. **单一职责** — 每个 Agent 只负责一个决策层级
3. **容错优先** — 每个 Agent 都有 fallback 值，LLM 不可用时系统仍可运行（降级为启发式规则）
4. **结构化输出** — 全部使用 `json_object` 模式，便于程序化消费
5. **低温度** — `temperature=0.1` 确保金融决策的确定性和可复现性
