"""MacroAgent --- Layer 1: market phase & risk appetite assessment."""

import pandas as pd

from paper_trading.agents.base import BaseAgent

MACRO_SYSTEM_PROMPT = (
    "You are a macro market analyst. Always return valid JSON only."
)

MACRO_USER_TEMPLATE = """
Today is {target_date} before market open.
Based on the following data, judge the current market phase and provide a risk appetite score.

[Macro Data]
- S&P 500 (SPY) last 5 days return : {spy_5d}%
- S&P 500 (SPY) last 20 days return: {spy_20d}%
- Market Volatility (VIX) recent average (5d): {vix_val}
- VIX trend (5d change): {vix_trend}

Classification guide:
- Bull   : sustained uptrend, low VIX (<20), positive momentum
- Bear   : sustained downtrend, elevated VIX (>25), negative momentum
- Ranging: sideways movement, moderate VIX
- Panic  : sharp drawdown, VIX spike (>35), extreme fear

Output strictly as JSON:
{{
    "market_phase": "Bull" | "Bear" | "Ranging" | "Panic",
    "risk_appetite": <integer 0-10, where 10 is extremely greedy>,
    "reasoning": "<one sentence citing specific data points>"
}}
"""


class MacroAgent(BaseAgent):
    """Assess macro environment from SPY and VIX data."""

    def __init__(self):
        super().__init__(name="MacroAgent", system_prompt=MACRO_SYSTEM_PROMPT)

    def assess(self, data: pd.DataFrame, target_date: str) -> dict:
        spy = data["SPY"]
        vix = data["^VIX"]

        spy_5d = (spy.iloc[-1] / spy.iloc[-5] - 1) * 100 if len(spy) >= 5 else 0
        spy_20d = (spy.iloc[-1] / spy.iloc[-20] - 1) * 100 if len(spy) >= 20 else 0
        vix_avg = vix.tail(5).mean()
        vix_trend = vix.iloc[-1] - vix.iloc[-5] if len(vix) >= 5 else 0

        prompt = MACRO_USER_TEMPLATE.format(
            target_date=target_date,
            spy_5d=round(spy_5d, 2),
            spy_20d=round(spy_20d, 2),
            vix_val=round(vix_avg, 2),
            vix_trend=round(vix_trend, 2),
        )
        result = self.call_llm(prompt)
        return result or {
            "market_phase": "Ranging",
            "risk_appetite": 5,
            "reasoning": "LLM unavailable",
        }
