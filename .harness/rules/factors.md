# 24 因子规格说明

## 概述

回测引擎内置 5 大类共 24 个技术因子，统一由 `FactorLibrary` 计算。每个因子输出一个 `pd.DataFrame`（行=交易日，列=ticker），值域归一化到 `[-1, 1]`。

## 因子总览

| # | 因子名称 | 类别 | 方向 | 说明 |
|---|---|---|---|---|
| 1 | sma_crossover_20_50 | 趋势 | +1=看多 | SMA20 与 SMA50 的偏离度 |
| 2 | sma_crossover_50_200 | 趋势 | +1=看多 | 金叉/死叉信号 (SMA50 vs SMA200) |
| 3 | ema_crossover_12_26 | 趋势 | +1=看多 | EMA12 与 EMA26 交叉 (MACD 方向) |
| 4 | adx_14 | 趋势 | +1=强趋势 | ADX 趋势强度 + 方向 (基于 +DI/-DI) |
| 5 | rsi_14 | 动量 | -1=超买 | RSI 反转信号 (超买→卖, 超卖→买) |
| 6 | macd_signal | 动量 | +1=看多 | MACD 线与信号线的标准化差值 |
| 7 | macd_histogram | 动量 | +1=加速 | MACD 柱状图的加速度 (diff of histogram) |
| 8 | momentum_20d | 动量 | +1=正动量 | 20 日收益率 z-score |
| 9 | momentum_60d | 动量 | +1=正动量 | 60 日收益率 z-score |
| 10 | momentum_120d | 动量 | +1=正动量 | 120 日收益率 z-score |
| 11 | stochastic_14 | 动量 | +1=超卖反弹 | Stochastic %K 反转信号 |
| 12 | cci_20 | 动量 | -1=超买 | CCI 反转信号 (+100 超买, -100 超卖) |
| 13 | williams_r_14 | 动量 | +1=超卖反弹 | Williams %R 反转信号 |
| 14 | bollinger_position | 波动 | -1=上轨 | 价格在布林带中的位置 (上轨→超买) |
| 15 | bollinger_squeeze | 波动 | +1=收缩 | 布林带宽度的 z-score (收缩=突破前兆) |
| 16 | volatility_20d | 波动 | -1=高波动 | 20 日年化波动率 z-score (高波=风险) |
| 17 | volatility_regime | 波动 | -1=高波区间 | 波动率在 252 日中的百分位排名 |
| 18 | atr_14 | 波动 | -1=高 ATR | ATR(14) 占价格百分比 z-score |
| 19 | volume_ratio | 成交量 | — | 当日量 / 20 日均量 (当前返回 0，待实现) |
| 20 | volume_price_trend | 成交量 | +1=积累 | 价格收益率 × 成交量的 20 日滚动和 z-score |
| 21 | obv_trend | 成交量 | +1=上升 | OBV 趋势简化 (价格 5 日收益的 20 日均值 z-score) |
| 22 | beta_spy | 风险 | -1=高 Beta | 60 日滚动 Beta 偏离 1.0 的程度 |
| 23 | return_5d_reversal | 风险 | +1=超跌反弹 | 5 日反转信号 (跌→买, 涨→卖) |
| 24 | drawdown_60d | 风险 | +1=超跌反弹 | 60 日内最大回撤的均值回复信号 |

## 类别说明

### 趋势类 (4 个)

判断价格方向性运动。输出基于均线交叉或趋势强度指标。

| 因子 | 公式 | 归一化 | 解读 |
|---|---|---|---|
| sma_crossover_20_50 | `(SMA20 - SMA50) / SMA50` | `clip(x × 20, -1, 1)` | >0 短期均线在长期上方 |
| sma_crossover_50_200 | `(SMA50 - SMA200) / SMA200` | `clip(x × 10, -1, 1)` | >0 金叉区域 |
| ema_crossover_12_26 | `(EMA12 - EMA26) / EMA26` | `clip(x × 20, -1, 1)` | 同 MACD 方向 |
| adx_14 | `(+DI - -DI) / 100 × ADX / 50` | `clip(raw, -1, 1)` | >0 上升趋势强劲 |

### 动量类 (9 个)

衡量价格变化速度与超买超卖状态。

| 因子 | 公式 | 归一化 | 解读 |
|---|---|---|---|
| rsi_14 | 标准 RSI(14) | `clip((50 - RSI) / 20, -1, 1)` | >0 RSI<50 (超卖反弹机会) |
| macd_signal | `(MACD - Signal) / std(63d)` | `clip(zscore, -1, 1)` | >0 MACD 在信号线上方 |
| macd_histogram | `diff(MACD_histogram) / std(63d)` | `clip(zscore, -1, 1)` | >0 柱状图加速上升 |
| momentum_20d | `pct_change(20) × 100` | `zscore(252d), clip(-1,1)` | 20 日动量标准化 |
| momentum_60d | `pct_change(60) × 100` | `zscore(252d), clip(-1,1)` | 60 日动量标准化 |
| momentum_120d | `pct_change(120) × 100` | `zscore(252d), clip(-1,1)` | 120 日动量标准化 |
| stochastic_14 | `%K = 100 × (C-L14)/(H14-L14)` | `clip((50 - %K) / 30, -1, 1)` | >0 Stochastic 低位 |
| cci_20 | `(TP - SMA20) / (0.015 × MAD)` | `clip(-CCI / 100, -1, 1)` | >0 CCI 在 -100 下方 (超卖) |
| williams_r_14 | `%R = -100 × (H14-C)/(H14-L14)` | `clip((%R + 50) / 30, -1, 1)` | >0 %R 在 -80 下方 (超卖) |

### 波动类 (5 个)

衡量价格波动幅度，高波动通常视为风险信号。

| 因子 | 公式 | 归一化 | 解读 |
|---|---|---|---|
| bollinger_position | `(Price - SMA20) / (2 × σ20)` | `clip(-pos × 2, -1, 1)` | >0 价格在下轨 (超卖) |
| bollinger_squeeze | `BW = 2σ20 / SMA20` | `zscore(BW, 63d), clip(-1,1)` | >0 带宽收缩 (突破前兆) |
| volatility_20d | `σ20 × √252` | `-zscore(252d), clip(-1,1)` | >0 波动低于均值 |
| volatility_regime | `σ20 在 252 日中的百分位` | `clip(1 - rank×2, -1, 1)` | >0 处于低波动区间 |
| atr_14 | `ATR(14) / Price` | `-zscore(252d), clip(-1,1)` | >0 ATR 低于均值 |

### 成交量类 (3 个)

结合价格与成交量判断资金流向。

| 因子 | 公式 | 归一化 | 解读 |
|---|---|---|---|
| volume_ratio | `Volume / SMA(Volume, 20)` | — | 当前返回 0 (待实现) |
| volume_price_trend | `Σ(return × vol_ratio, 20d) × 100` | `zscore(252d), clip(-1,1)` | >0 量价齐升 (积累) |
| obv_trend | `SMA(pct_change(5d), 20)` | `zscore(252d), clip(-1,1)` | >0 OBV 趋势向上 |

### 风险/其他 (3 个)

衡量系统性风险和极端事件后的反转机会。

| 因子 | 公式 | 归一化 | 解读 |
|---|---|---|---|
| beta_spy | `60 日滚动 Cov(r, r_SPY) / Var(r_SPY)` | `clip((β-1)/0.5, -1, 1)` | >0 Beta>1 (高弹性) |
| return_5d_reversal | `pct_change(5d) × 100` | `-zscore(252d), clip(-1,1)` | >0 近 5 日下跌 (反弹候选) |
| drawdown_60d | `(Price / max(60d) - 1) × 100` | `-zscore(252d), clip(-1,1)` | >0 深度回撤 (均值回复) |

## 通用约定

- **方向符号**：正值偏向看多（BUY），负值偏向看空（SELL）
- **阈值过滤**：因子值在 `(threshold_short, threshold_long)` 区间内时视为 0（中性信号），避免噪音
- **权重符号**：`direction × weight` 决定因子对复合信号的贡献方向和强度
- **缺失数据处理**：`rolling` 窗口期内数据不足返回 `NaN`，`zscore` 计算最小要求 63 个数据点
