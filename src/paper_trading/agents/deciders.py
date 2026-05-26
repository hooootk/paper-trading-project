"""Prompt templates for the backtest decider and frequency decider.

These are used by TradingAgent methods: decide_backtest() and decide_rebalance_frequency().
"""

BACKTEST_DECISION_PROMPT = (
    "You are a quantitative strategy auditor. Always return valid JSON only."
)

BACKTEST_DECISION_TEMPLATE = """
Today is {target_date}.
Current market conditions:
- Market phase: {market_phase}
- Risk appetite: {risk_appetite}/10
- Risk level: {risk_level}
- Portfolio risk action: {risk_action}
- VIX current: {vix_val}

Last backtest run: {last_backtest}

Our BacktestEngine evaluates strategies built from 24 technical factors across 5 categories:
  Trend      -- sma_crossover_20_50, sma_crossover_50_200, ema_crossover_12_26, adx_14
  Momentum   -- rsi_14, macd_signal, macd_histogram, momentum_20d/60d/120d, stochastic_14, cci_20, williams_r_14
  Volatility -- bollinger_position, bollinger_squeeze, volatility_20d, volatility_regime, atr_14
  Volume     -- volume_ratio, volume_price_trend, obv_trend
  Risk/Other -- beta_spy, return_5d_reversal, drawdown_60d

Each strategy selects a subset with custom weights, thresholds, and direction.
Backtest results include: Sharpe, Calmar, Sortino, MaxDD, Volatility, Beta, WinRate, P/L Ratio, ProfitFactor.

Criteria for triggering a backtest:
- Market phase is Panic or Bear (regime stress) -> STRONGLY trigger -- strategies calibrated in Bull may fail
- Risk level is "High" and last backtest >30 days ago -> trigger (stale data in new risk regime)
- VIX > 30 (elevated volatility) -> trigger stress-test backtest across all strategies
- VIX > 40 -> strongly trigger with urgency=high, recommend all strategies
- Normal conditions (Bull/Ranging, low VIX) but no backtest in >60 days -> optionally trigger a refresh
- Bull market, low VIX, recent backtest (<30 days) with good metrics -> skip

Output strictly as JSON:
{{
    "should_backtest": true | false,
    "urgency": "high" | "medium" | "low",
    "reasoning": "<one sentence citing the specific market condition + factor categories of concern>",
    "recommended_strategies": "<indices e.g. '0,1,2' or 'all'>"
}}
"""

FREQUENCY_DECISION_TEMPLATE = """
Today is {target_date}.
Current market conditions:
- Market phase: {market_phase}
- Risk appetite: {risk_appetite}/10
- Risk level: {risk_level}
- VIX current: {vix_val}
- SPY 20-day realized volatility (ann.): {spy_vol}%
- SPY 60-day trend strength (|ret|/vol): {trend_strength}

Rebalance frequency options:
- daily   : rebalance every trading day -- highest turnover, fastest reaction
- weekly  : rebalance every 5 trading days
- biweekly: rebalance every 10 trading days
- monthly : rebalance every 21 trading days -- lowest turnover, slowest reaction

Decision framework:
- VIX > 35 OR market_phase == "Panic" -> daily (extreme conditions, need daily adjustments)
- VIX > 25 OR market_phase == "Bear" -> weekly or daily (elevated risk, more frequent checks)
- VIX 15-25, market_phase == "Ranging" -> weekly or biweekly (mean-reversion opportunities, moderate turnover)
- VIX < 15, market_phase == "Bull", trend_strength > 1.0 -> monthly (stable uptrend, let winners run)
- High realized volatility (spy_vol > 30%) -> favour higher frequency regardless of other signals
- Risk level "High" -> favour higher frequency to respond quickly
- Low volatility + strong trend -> favour lower frequency (reduce trading costs)

Output strictly as JSON:
{{
    "recommended_frequency": "daily" | "weekly" | "biweekly" | "monthly",
    "confidence": <float 0.0-1.0>,
    "reasoning": "<one sentence citing VIX, market phase, volatility, and trend strength>"
}}
"""

INTENT_RECOGNITION_SYSTEM = (
    "You are an intent classifier for a paper trading system. "
    "Always return valid JSON only."
)

INTENT_RECOGNITION_TEMPLATE = """
You are an intent classifier for a Paper Trading Agent system.

Available functions (with their option numbers):

[1] LLM Multi-Agent Trading (Dry Run) --- Run the full LLM pipeline (Macro -> StockAnalyst -> RiskManager) and compute target weights, but do NOT submit orders. Keywords: AI分析, LLM分析, 模拟分析, 多智能体分析, dry run, analyze with AI, paper analysis, 看看AI怎么说, 用AI分析一下行情, 试算, 分析一下

[2] LLM Multi-Agent Trading (Real Orders) --- Run the full LLM pipeline AND submit real orders to Alpaca paper account. Keywords: AI下单, LLM交易, 多智能体交易, real orders, AI trade, execute with AI, 让AI交易, 用AI实盘, AI实盘交易

[3] Strategy-Based Trading (Dry Run) --- Run a single rule-based strategy from strategy_config.json without submitting orders. Keywords: 策略模拟, 策略试算, 因子策略, rule-based dry run, 用策略分析, 跑因子, 因子分析

[4] Strategy-Based Trading (Real Orders) --- Run a single rule-based strategy AND submit real orders. Keywords: 策略下单, 因子实盘, 策略实盘交易, rule-based real orders, execute strategy, 用策略交易

[5] Backtest All Strategies --- Run backtesting on ALL strategies and show performance comparison. Keywords: 回测所有, 全部回测, 回测全部策略, backtest all, run all backtests, 跑回测, 回测一下, 回测

[6] Backtest Single Strategy --- Run backtesting on ONE specific strategy by index. Keywords: 回测单个, 回测某一个, 指定策略回测, backtest one, single backtest, 回测策略N

[7] Live Trading + Auto Backtest --- Run LLM live trading plus let the agent decide whether to trigger backtests. Keywords: 自动回测, 交易加回测, auto backtest, live plus backtest

[8] Regenerate Strategy Config --- Generate new random strategies in strategy_config.json. Keywords: 生成策略, 重新生成, 创建策略, generate strategies, create config, 生成配置, 新策略, 重新生成配置

[9] View Alpaca Account Summary --- Show current Alpaca paper account balance, positions, P&L. Keywords: 查看账户, 账户摘要, 持仓, 余额, account summary, view account, 我的账户, 账户情况, 仓位

[10] LLM Rebalance Frequency Analysis --- Use LLM to recommend optimal rebalance frequency. Keywords: 调仓频率, 再平衡频率, rebalance frequency, 多久调仓, 调仓周期

[11] Multi-Strategy Parallel Trading --- Run 2+ strategies simultaneously with capital split. Keywords: 多策略并行, 组合策略, 多个策略一起, parallel strategies, multi-strategy, 策略组合, 多策略

[12] Manage TP/SL (Attach + Status Check) --- Check TP/SL thresholds and attach orders. Keywords: 止盈止损, 设置止盈, 止损, TP/SL, take profit, stop loss, 盈亏管理

[13] Auto-Select Best Strategy & Trade --- Backtest all, rank, pick best, and trade. Keywords: 自动选最优, 最优策略, 自动选择策略, 选最好的, auto select best, best strategy, 智能选策略

Rules:
- Return the MOST SPECIFIC option(s) that match the user's intent.
- matched_options is a list of integers (empty list [] if nothing matches at all).
- If the user mentions "交易" or "下单" or "实盘", prefer Real Orders variants [2], [4] over dry run [1], [3].
- If the user says only "回测" without qualifiers, default to [5] (backtest all).
- If the user mentions a strategy number like "策略3" or "strategy 2", include [3] or [6].
- Confidence should reflect how certain the match is (>0.8 = very clear, 0.5-0.8 = reasonable, <0.5 = uncertain).
- If the request is too vague to determine a specific function, return multiple plausible options.
- If the request has nothing to do with trading/backtesting/strategies, return empty list.

User input: "{user_text}"

Output strictly as JSON:
{{
    "matched_options": [<list of integers>],
    "confidence": <float 0.0-1.0>,
    "reasoning": "<one sentence in Chinese explaining the match>"
}}
"""
