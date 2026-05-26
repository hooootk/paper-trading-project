"""RiskManagerAgent --- Layer 3: portfolio-level risk assessment."""

import numpy as np
import pandas as pd

from paper_trading.agents.base import BaseAgent

RISK_SYSTEM_PROMPT = (
    "You are a Chief Risk Officer. Always return valid JSON only."
)

RISK_USER_TEMPLATE = """
Today is {target_date}.
Portfolio holdings: {portfolio_holdings}.

[Quantitative Risk Metrics]
- S&P 500 rolling 252-day Max Drawdown: {max_dd}%
- Estimated Portfolio VaR (95%, 1-day): {var_95}%
- Current VIX: {vix_val}
- Portfolio 20-day rolling volatility (annualised): {port_vol}%

[Backtest Performance Summary]
{backtest_summary}

Decision thresholds:
- VaR < -2% OR Max Drawdown < -15% OR VIX > 35 -> consider Reduce/Liquidate
- VIX > 40 OR Max Drawdown < -25% -> Liquidate All Long Positions
- If backtest shows Sharpe < 0 and MaxDD > 20%, current strategy config is fragile -> escalate risk level
- If backtest ProfitFactor < 1.0, the strategy is losing in historical simulation -> recommend Reduce
- If no backtest data exists, assume strategies are unproven -> be more conservative with exposure

Output strictly as JSON:
{{
    "risk_level": "Low" | "Medium" | "High",
    "action"    : "Hold Normally" | "Reduce Overall Exposure" | "Liquidate All Long Positions",
    "reasoning" : "<explain how VaR, VIX, Drawdown, Volatility and backtest results influenced the decision>"
}}
"""


class RiskManagerAgent(BaseAgent):
    """Assess portfolio-level risk and recommend action."""

    def __init__(self):
        super().__init__(name="RiskManagerAgent", system_prompt=RISK_SYSTEM_PROMPT)

    def assess(self, data: pd.DataFrame, tickers: list, target_date: str,
               backtest_summary: str = "No backtest data available.") -> dict:
        spy_1y = data["SPY"].tail(252)
        max_dd = ((spy_1y / spy_1y.cummax() - 1) * 100).min()

        port_returns = data[tickers].pct_change().dropna()
        eq_weighted = port_returns.mean(axis=1)
        var_95 = np.percentile(eq_weighted, 5) * 100
        port_vol = eq_weighted.tail(20).std() * np.sqrt(252) * 100
        vix_val = data["^VIX"].iloc[-1]

        prompt = RISK_USER_TEMPLATE.format(
            target_date=target_date,
            portfolio_holdings=", ".join(tickers),
            max_dd=round(max_dd, 2),
            var_95=round(var_95, 2),
            vix_val=round(vix_val, 2),
            port_vol=round(port_vol, 2),
            backtest_summary=backtest_summary,
        )
        result = self.call_llm(prompt)
        return result or {
            "risk_level": "Medium",
            "action": "Hold Normally",
            "reasoning": "LLM unavailable",
        }
