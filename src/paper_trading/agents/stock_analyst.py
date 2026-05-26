"""StockAnalystAgent --- Layer 2: per-ticker signal generation."""

from paper_trading.agents.base import BaseAgent

STOCK_SYSTEM_PROMPT = (
    "You are a quantitative analyst. Always return valid JSON only."
)

STOCK_USER_TEMPLATE = """
Today is {target_date} before market open.
Current macro environment: {market_phase}, risk appetite {risk_appetite}/10.

Evaluate {ticker} based ONLY on the historical data below -- no future information.

[Technical & Price/Volume Data for {ticker}]
{tech_data}

[Backtest Context for {ticker}]
{backtest_context}

Indicator interpretation guide:
- ema12 vs ema26       : EMA12 > EMA26 = bullish momentum (like MACD direction)
- rsi14                 : >70 overbought, <30 oversold, 30-70 neutral
- macd_line vs signal   : line > signal = bullish crossover; histogram turning positive = accelerating
- stoch_k_14            : >80 overbought, <20 oversold
- bb_position           : -1 = at lower band (oversold/mean-reversion buy), +1 = at upper band (overbought)
- atr_14                : higher = more volatile, position size accordingly
- drawdown_60d_pct      : large negative = potential bounce candidate
- volume_price_trend    : positive = accumulation, negative = distribution

Our BacktestEngine supports 24 factors across categories:
  Trend: sma_crossover_20_50, sma_crossover_50_200, ema_crossover_12_26, adx_14
  Momentum: rsi_14, macd_signal, macd_histogram, momentum_20d/60d/120d, stochastic_14, cci_20, williams_r_14
  Volatility: bollinger_position, bollinger_squeeze, volatility_20d, volatility_regime, atr_14
  Volume: volume_ratio, volume_price_trend, obv_trend
  Risk/Other: beta_spy, return_5d_reversal, drawdown_60d

Rules:
- In Panic regimes, default to HOLD or SELL unless technical indicators are strongly positive across multiple factor categories.
- In Bull regimes with risk_appetite >= 7, favour BUY when ema12 > ema26, macd_histogram is positive, price > sma20, and stoch_k is not overbought (>80).
- In Bear regimes, only BUY if rsi14 < 30 (deeply oversold) AND drawdown_60d < -15% (capitulation).
- In Ranging, use mean-reversion: BUY at bb_position < -0.8, SELL at bb_position > +0.8.
- Confidence must reflect the consistency of signals across all three categories (trend + momentum + volatility).
- When backtest_context is available, use it to calibrate confidence (e.g. if backtest Sharpe < 0, lower confidence; if profit_factor > 1.5, raise confidence).

Output strictly as JSON:
{{
    "signal"    : "BUY" | "SELL" | "HOLD",
    "confidence": <float 0.0-1.0>,
    "reasoning" : "<one sentence citing specific indicators, macro context, and backtest results if available>"
}}
"""


class StockAnalystAgent(BaseAgent):
    """Generate a trading signal for a single stock."""

    def __init__(self):
        super().__init__(name="StockAnalystAgent", system_prompt=STOCK_SYSTEM_PROMPT)

    def analyze(self, ticker: str, tech_data: dict, market_phase: str,
                risk_appetite: int, target_date: str, backtest_context: str = "No backtest data available.") -> dict:
        tech_str = "\n".join(f"  {k}: {v}" for k, v in tech_data.items())
        prompt = STOCK_USER_TEMPLATE.format(
            target_date=target_date,
            market_phase=market_phase,
            risk_appetite=risk_appetite,
            ticker=ticker,
            tech_data=tech_str,
            backtest_context=backtest_context,
        )
        result = self.call_llm(prompt)
        return result or {
            "signal": "HOLD",
            "confidence": 0.0,
            "reasoning": "LLM unavailable",
        }
