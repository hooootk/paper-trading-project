# 信号逻辑与仓位管理

## 概述

策略回测和规则交易中，24 个因子的原始值通过信号逻辑聚合成每只股票的综合评分，再通过仓位管理方法转化为目标持仓权重。

## 信号逻辑 (signal_logic)

策略配置中的 `signal_logic` 字段决定如何从多因子信号得出最终交易决策。

### weighted_sum（加权求和，默认）

```
composite_score[ticker] = Σ factor_value × direction × weight / Σ|weight|
```

- 每个因子的原始值乘以 `direction`（+1 或 -1）和 `weight`
- 因子值在 `(threshold_short, threshold_long)` 区间内的置零
- 除以总绝对权重做归一化
- 结果范围约 `[-1, 1]`

**评分映射**：

| composite_score | 信号 | 置信度 |
|---|---|---|
| > 0.2 | BUY | min(score × 2, 1.0) |
| < -0.2 | SELL | min(abs(score) × 2, 1.0) |
| [-0.2, 0.2] | HOLD | 0.3 |

### majority_vote（多数投票）

当前实现同 `weighted_sum`。预留扩展：每因子独立投票（BUY/SELL/HOLD），取票数最多的方向。

### top_n（前 N 选股）

当前实现同 `weighted_sum`。预留扩展：按 composite_score 降序排列，仅选取得分最高的前 N 只。

## 仓位管理 (position_sizing)

策略配置中的 `position_sizing` 字段决定如何将信号评分转化为持仓权重。

### equal_weight（等权重）

```
weight[ticker] = 1 / N   (N = 入选股票数)
```

- 所有正信号股票均分资金
- 最简单，分散度高
- 忽略信号强弱差异

### factor_score（因子评分加权）

```
weight[ticker] = composite_score[ticker] / Σ composite_score
```

- 信号越强，分配资金越多
- 适合对信号质量有信心的策略

### risk_parity（风险平价）

```
weight[ticker] = (1 / volatility[ticker]) / Σ (1 / volatility)
```

- 计算每只股票 60 日波动率的倒数
- 低波动股票获得更高权重
- 目标：每个持仓对组合的风险贡献相等

## 调仓频率 (rebalance_frequency)

| 配置值 | 交易日间隔 | 适用场景 |
|---|---|---|
| daily | 1 | 高频策略、高波动市场 |
| weekly | 5 | 中期策略、适度周转 |
| biweekly | 10 | 平衡型策略 |
| monthly | 21 | 低频策略、趋势跟踪 |

**LLM 调仓频率决策**：`TradingAgent.decide_rebalance_frequency()` 基于 VIX、市场阶段、SPY 波动率和趋势强度，由 LLM 推荐最优频率。策略规则交易中，策略配置的频率可能与 LLM 推荐冲突——此时以策略配置为准，LLM 建议仅供提示。

## 风控覆盖

无论使用哪种信号逻辑和仓位管理方式，风控评估结果会统一覆盖：

| 风控 action | 效果 |
|---|---|
| Hold Normally | 无覆盖，使用原始权重 |
| Reduce Overall Exposure | 所有权重 × 0.5 |
| Liquidate All Long Positions | 所有权重 = 0 |

## 最大持仓限制

`max_positions` 参数限制同时持有的股票数量：

- 按 composite_score 降序排列
- 仅保留前 `max_positions` 只正信号股票
- 其余股票权重 = 0

## 策略配置完整示例

```json
{
  "name": "strategy_1",
  "start_date": "2021-01-01",
  "end_date": "2023-06-30",
  "tickers": ["AAPL", "MSFT", "NVDA", "JPM", "XOM"],
  "initial_capital": 100000,
  "signal_logic": "majority_vote",
  "rebalance_frequency": "biweekly",
  "position_sizing": "equal_weight",
  "max_positions": 5,
  "factors": {
    "rsi_14": {
      "weight": 0.65,
      "direction": -1,
      "threshold_long": 0.12,
      "threshold_short": -0.39
    }
  }
}
```

**字段说明**：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| name | str | 是 | 策略唯一标识 |
| start_date | str | 是 | 回测开始日期 YYYY-MM-DD |
| end_date | str | 是 | 回测结束日期，与 start 间隔 ≥ 2 年 |
| tickers | list[str] | 是 | 股票池，至少 1 只 |
| initial_capital | int | 是 | 初始资金 |
| signal_logic | str | 否 | weighted_sum / majority_vote / top_n，默认 weighted_sum |
| rebalance_frequency | str | 否 | daily / weekly / biweekly / monthly，默认 monthly |
| position_sizing | str | 否 | equal_weight / factor_score / risk_parity，默认 equal_weight |
| max_positions | int | 否 | 最大持仓数，默认 10 |
| factors | dict | 是 | 因子配置，至少 1 个，键名必须在 24 因子池内 |

**因子子字段**：

| 字段 | 类型 | 说明 |
|---|---|---|
| weight | float | 因子权重，建议 0.3-1.5 |
| direction | int | +1 正向（因子值大→看多），-1 反向（因子值大→看空） |
| threshold_long | float | 做多阈值，因子值低于此值视为中性 |
| threshold_short | float | 做空阈值（负值），因子值高于此值视为中性 |
