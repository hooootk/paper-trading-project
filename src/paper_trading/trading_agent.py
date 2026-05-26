"""TradingAgent --- orchestrator for the full paper-trading pipeline.

Coordinates DataAgent, MacroAgent, StockAnalystAgent, RiskManagerAgent,
AlpacaExecutor, and BacktestEngine.
"""

import json
import time
from datetime import datetime

import numpy as np
import pandas as pd

from paper_trading.agents.base import BaseAgent
from paper_trading.agents.data import DataAgent
from paper_trading.agents.macro import MacroAgent
from paper_trading.agents.stock_analyst import StockAnalystAgent
from paper_trading.agents.risk_manager import RiskManagerAgent
from paper_trading.agents.deciders import (
    BACKTEST_DECISION_PROMPT,
    BACKTEST_DECISION_TEMPLATE,
    FREQUENCY_DECISION_TEMPLATE,
)
from paper_trading.backtest_engine import (
    BacktestEngine as BTEngine,
    StrategyConfig,
    FactorLibrary,
)
from paper_trading.config import settings
from paper_trading.executor import ALPACA_AVAILABLE, AlpacaExecutor


class TradingAgent:
    """Orchestrator agent that runs the full paper-trading pipeline."""

    def __init__(self, tickers: list[str] | None = None):
        self.tickers = tickers or settings.get_portfolio_tickers()
        self.data_agent = DataAgent()
        self.macro_agent = MacroAgent()
        self.stock_agent = StockAnalystAgent()
        self.risk_agent = RiskManagerAgent()
        self.executor: AlpacaExecutor | None = None

        self.raw_data: pd.DataFrame | None = None
        self.market_state: dict = {}
        self.stock_signals: dict = {}
        self.risk_assessment: dict = {}
        self.target_weights: dict = {}

        self.backtest_results: list = []
        self.last_backtest_date: str = ""

        self.frequency_decision: dict = {}
        self.strategy_mode: bool = False
        self.active_strategy: dict | None = None

    # --- public API --------------------------------------------------------

    def run(self, target_date: str = "", dry_run: bool = True):
        """Run the full LLM pipeline and optionally execute trades."""
        target_date = target_date or datetime.today().strftime("%Y-%m-%d")
        print(f"\n{'='*60}")
        print(f"  TradingAgent | {target_date}")
        print(f"{'='*60}")

        self.raw_data = self.data_agent.fetch_market_data(
            self.tickers, settings.backtest_start, target_date
        )
        end_dt = pd.to_datetime(target_date)
        hist = self.raw_data[self.raw_data.index < end_dt].copy()

        print(f"  -- Macro --")
        self.market_state = self.macro_agent.assess(hist, target_date)
        print(f"  Phase: {self.market_state['market_phase']}  "
              f"Appetite: {self.market_state['risk_appetite']}/10")

        print(f"  -- Signals --")
        for ticker in self.tickers:
            if ticker not in hist.columns:
                self.stock_signals[ticker] = {"signal": "HOLD", "confidence": 0.0,
                                              "reasoning": "No data"}
                continue
            tech = self.data_agent.technical_features(hist[ticker])
            bt_ctx = self._build_backtest_context(ticker)
            sig = self.stock_agent.analyze(
                ticker, tech,
                self.market_state["market_phase"],
                self.market_state["risk_appetite"],
                target_date,
                backtest_context=bt_ctx,
            )
            self.stock_signals[ticker] = sig
            print(f"    {ticker:<6} {sig.get('signal','?'):<5}  "
                  f"confidence={sig.get('confidence',0):.2f}")
            time.sleep(1.5)

        print(f"  -- Risk --")
        bt_summary = self._build_backtest_summary()
        self.risk_assessment = self.risk_agent.assess(hist, self.tickers, target_date, bt_summary)
        print(f"  Level: {self.risk_assessment['risk_level']}  "
              f"Action: {self.risk_assessment['action']}")

        print(f"  -- Rebalance Frequency --")
        self.frequency_decision = self.decide_rebalance_frequency(target_date)

        self.target_weights = self._compute_weights()

        if ALPACA_AVAILABLE:
            self.executor = AlpacaExecutor()
            self.executor.print_summary()
            self.executor.rebalance(self.target_weights, dry_run=dry_run)
        else:
            print("  [TradingAgent] Alpaca unavailable --- skipping execution.")

        return self.target_weights

    def _compute_weights(self) -> dict:
        action = self.risk_assessment.get("action", "Hold Normally")
        if action == "Liquidate All Long Positions":
            print(f"    Risk override: LIQUIDATE ALL")
            return {t: 0.0 for t in self.tickers}

        raw = {}
        for ticker, sig in self.stock_signals.items():
            if sig.get("signal") == "BUY":
                raw[ticker] = float(sig.get("confidence", 0.5))
            else:
                raw[ticker] = 0.0

        if action == "Reduce Overall Exposure":
            raw = {t: w * 0.5 for t, w in raw.items()}

        total = sum(raw.values())
        if total == 0:
            return {t: 1.0 / len(self.tickers) for t in self.tickers}
        return {t: w / total for t, w in raw.items()}

    # --- strategy-based trading (rule-based, no LLM) -----------------------

    def run_with_strategy(self, strategy_index: int, target_date: str = "",
                          dry_run: bool = True) -> dict:
        """Run paper trading using a strategy from strategy_config.json.

        This bypasses LLM agents entirely --- signals come from the 24-factor
        rule engine used by BacktestEngine (deterministic, fast, free).
        """
        strategies = StrategyConfig.load()
        if strategy_index < 0 or strategy_index >= len(strategies):
            raise IndexError(f"Strategy index {strategy_index} out of range (0-{len(strategies)-1})")

        strategy = strategies[strategy_index]
        StrategyConfig.validate(strategy)

        self.strategy_mode = True
        self.active_strategy = strategy
        self.tickers = strategy["tickers"]

        target_date = target_date or datetime.today().strftime("%Y-%m-%d")
        strategy_name = strategy["name"]

        print(f"\n{'='*60}")
        print(f"  STRATEGY TRADING MODE --- {strategy_name}")
        print(f"  Factors: {len(strategy['factors'])} | Logic: {strategy.get('signal_logic','weighted_sum')}")
        print(f"  Rebalance: {strategy.get('rebalance_frequency','monthly')} | "
              f"Sizing: {strategy.get('position_sizing','equal_weight')}")
        print(f"  '{strategy_name}' | {target_date}")
        print(f"{'='*60}")

        self.raw_data = self.data_agent.fetch_market_data(
            self.tickers, settings.backtest_start, target_date
        )
        end_dt = pd.to_datetime(target_date)
        hist = self.raw_data[self.raw_data.index < end_dt].copy()

        print(f"  -- Factor Signals (rule-based) --")
        benchmark = hist["SPY"] if "SPY" in hist.columns else hist.iloc[:, 0]
        ticker_prices = hist[[t for t in self.tickers if t in hist.columns]]
        self.tickers = [t for t in self.tickers if t in ticker_prices.columns]

        signals = self._compute_strategy_signals(strategy, ticker_prices, benchmark)

        self.stock_signals = {}
        self._raw_strategy_scores = signals
        for t in self.tickers:
            score = signals.get(t, 0.0)
            if score > 0.2:
                s, c = "BUY", min(score * 2, 1.0)
            elif score < -0.2:
                s, c = "SELL", min(abs(score) * 2, 1.0)
            else:
                s, c = "HOLD", 0.3
            self.stock_signals[t] = {
                "signal": s, "confidence": round(c, 2),
                "reasoning": f"Composite factor score: {score:.3f}",
            }
            print(f"    {t:<6} {s:<5}  score={score:+.3f}  confidence={c:.2f}")

        print(f"  -- Risk (LLM) --")
        bt_summary = self._build_backtest_summary()
        self.risk_assessment = self.risk_agent.assess(hist, self.tickers, target_date, bt_summary)
        print(f"  Level: {self.risk_assessment['risk_level']}  "
              f"Action: {self.risk_assessment['action']}")

        print(f"  -- Rebalance Frequency --")
        self.frequency_decision = self.decide_rebalance_frequency(target_date)
        strategy_freq = strategy.get("rebalance_frequency", "monthly")
        llm_freq = self.frequency_decision.get("recommended_frequency", "monthly")
        if strategy_freq != llm_freq:
            print(f"    Note: strategy uses '{strategy_freq}', LLM recommends '{llm_freq}'")

        self.target_weights = self._strategy_weights(strategy)

        if ALPACA_AVAILABLE:
            self.executor = AlpacaExecutor()
            self.executor.print_summary()
            self.executor.rebalance(self.target_weights, dry_run=dry_run)
        else:
            print("  [TradingAgent] Alpaca unavailable --- skipping execution.")

        return self.target_weights

    def _compute_strategy_signals(self, strategy: dict, prices: pd.DataFrame,
                                   benchmark: pd.Series) -> dict[str, float]:
        """Compute today's composite signal for each ticker using strategy factors."""
        factor_names = list(strategy["factors"].keys())
        factors_config = strategy["factors"]

        lib = FactorLibrary(prices, benchmark)
        all_factors = lib.compute_all_factors(factor_names)

        last_idx = prices.index[-1]
        composite = {t: 0.0 for t in prices.columns}
        total_weight = 0.0

        for fname, factor_df in all_factors.items():
            cfg = factors_config[fname]
            w = cfg.get("weight", 1.0)
            direction = cfg.get("direction", 1)
            thresh_long = cfg.get("threshold_long", 0.2)
            thresh_short = cfg.get("threshold_short", -0.2)

            if last_idx not in factor_df.index:
                continue
            row = factor_df.loc[last_idx]

            for t in prices.columns:
                if t not in row.index:
                    continue
                raw = row[t]
                if thresh_short < raw < thresh_long:
                    raw = 0.0
                composite[t] += raw * direction * w

            total_weight += abs(w)

        if total_weight > 0:
            composite = {t: v / total_weight for t, v in composite.items()}

        return composite

    def _strategy_weights(self, strategy: dict) -> dict[str, float]:
        """Convert raw composite factor scores to target weights."""
        position_sizing = strategy.get("position_sizing", "equal_weight")
        max_positions = strategy.get("max_positions", 10)

        action = self.risk_assessment.get("action", "Hold Normally")
        if action == "Liquidate All Long Positions":
            print(f"    Risk override: LIQUIDATE ALL")
            return {t: 0.0 for t in self.tickers}

        scores = getattr(self, "_raw_strategy_scores", {})
        if not scores:
            return {t: 1.0 / len(self.tickers) for t in self.tickers}

        candidates = [(t, s) for t, s in scores.items() if s > 0]
        candidates.sort(key=lambda x: -x[1])

        if not candidates:
            print(f"    No positive signals --- equal-weight all tickers")
            return {t: 1.0 / len(self.tickers) for t in self.tickers}

        top_n = min(max_positions, len(candidates))
        selected = {t: s for t, s in candidates[:top_n]}

        print(f"    Selected {len(selected)}/{len(self.tickers)} tickers "
              f"(max={max_positions}, sizing={position_sizing})")

        if position_sizing == "equal_weight":
            weights = {t: 1.0 / top_n for t in selected}
        elif position_sizing == "factor_score":
            total = sum(selected.values())
            weights = {t: s / total for t, s in selected.items()} if total > 0 else {}
        else:
            vols = {}
            if self.raw_data is not None:
                for t in selected:
                    if t in self.raw_data.columns:
                        rets = self.raw_data[t].pct_change().dropna()
                        vols[t] = rets.tail(60).std() if len(rets) > 20 else 0.02
                    else:
                        vols[t] = 0.02
            else:
                vols = {t: 0.02 for t in selected}
            inv_vol = {t: 1.0 / v for t, v in vols.items()}
            total_inv = sum(inv_vol.values())
            weights = {t: iv / total_inv for t, iv in inv_vol.items()} if total_inv > 0 else {}

        if action == "Reduce Overall Exposure":
            weights = {t: w * 0.5 for t, w in weights.items()}

        full_weights = {t: weights.get(t, 0.0) for t in self.tickers}
        return full_weights

    # --- backtest trigger --------------------------------------------------

    def decide_backtest(self, target_date: str = "") -> dict:
        """Use LLM + current market state to decide whether to trigger backtesting."""
        target_date = target_date or datetime.today().strftime("%Y-%m-%d")

        market_phase = self.market_state.get("market_phase", "Unknown")
        risk_appetite = self.market_state.get("risk_appetite", 5)
        risk_level = self.risk_assessment.get("risk_level", "Unknown")
        risk_action = self.risk_assessment.get("action", "Unknown")

        vix_val = "N/A"
        if self.raw_data is not None and "^VIX" in self.raw_data.columns:
            vix_val = str(round(self.raw_data["^VIX"].iloc[-1], 2))

        last_bt = self.last_backtest_date if self.last_backtest_date else "Never"
        prompt = BACKTEST_DECISION_TEMPLATE.format(
            target_date=target_date,
            market_phase=market_phase,
            risk_appetite=risk_appetite,
            risk_level=risk_level,
            risk_action=risk_action,
            vix_val=vix_val,
            last_backtest=last_bt,
        )

        decider = BaseAgent(name="BacktestDecider", system_prompt=BACKTEST_DECISION_PROMPT)
        result = decider.call_llm(prompt)

        if result is None:
            vix_num = float(vix_val) if vix_val != "N/A" else 20
            should = (market_phase in ("Panic", "Bear")) or (vix_num > 30)
            result = {
                "should_backtest": should,
                "urgency": "high" if vix_num > 40 else "medium",
                "reasoning": "Heuristic fallback --- LLM unavailable",
                "recommended_strategies": "all",
            }

        print(f"\n  [BacktestDecider] should_backtest={result.get('should_backtest')}  "
              f"urgency={result.get('urgency')}  reasoning={result.get('reasoning')}")
        return result

    def decide_rebalance_frequency(self, target_date: str = "") -> dict:
        """Use LLM + current market state to recommend rebalance frequency."""
        target_date = target_date or datetime.today().strftime("%Y-%m-%d")

        market_phase = self.market_state.get("market_phase", "Unknown")
        risk_appetite = self.market_state.get("risk_appetite", 5)
        risk_level = self.risk_assessment.get("risk_level", "Unknown")

        vix_val = "N/A"
        spy_vol = "N/A"
        trend_strength = "N/A"
        if self.raw_data is not None:
            if "^VIX" in self.raw_data.columns:
                vix_val = str(round(self.raw_data["^VIX"].iloc[-1], 2))
            if "SPY" in self.raw_data.columns:
                spy_ret = self.raw_data["SPY"].pct_change().dropna()
                spy_vol = str(round(spy_ret.tail(20).std() * np.sqrt(252) * 100, 2))
                ret_60d = self.raw_data["SPY"].iloc[-1] / self.raw_data["SPY"].iloc[-60] - 1
                vol_60d = spy_ret.tail(60).std() * np.sqrt(252)
                trend_strength = str(round(abs(ret_60d) / vol_60d, 2)) if vol_60d > 0 else "N/A"

        prompt = FREQUENCY_DECISION_TEMPLATE.format(
            target_date=target_date,
            market_phase=market_phase,
            risk_appetite=risk_appetite,
            risk_level=risk_level,
            vix_val=vix_val,
            spy_vol=spy_vol,
            trend_strength=trend_strength,
        )

        decider = BaseAgent(name="FrequencyDecider", system_prompt=(
            "You are a portfolio rebalancing strategist. Always return valid JSON only."
        ))
        result = decider.call_llm(prompt)

        if result is None:
            vix_num = float(vix_val) if vix_val != "N/A" else 20
            if vix_num > 35 or market_phase == "Panic":
                freq = "daily"
            elif vix_num > 25 or market_phase == "Bear":
                freq = "weekly"
            elif vix_num < 15 and market_phase == "Bull":
                freq = "monthly"
            else:
                freq = "biweekly"
            result = {
                "recommended_frequency": freq,
                "confidence": 0.5,
                "reasoning": f"Heuristic fallback --- VIX={vix_val}, phase={market_phase}",
            }

        print(f"\n  [FrequencyDecider] recommended={result.get('recommended_frequency')}  "
              f"confidence={result.get('confidence')}  reasoning={result.get('reasoning')}")
        return result

    def _build_backtest_summary(self) -> str:
        """Summarize all backtest results for the risk manager."""
        if not self.backtest_results:
            return "No backtest data available."
        lines = [f"Last backtest: {self.last_backtest_date}",
                 f"Strategies evaluated: {len(self.backtest_results)}"]
        for r in self.backtest_results:
            m = r.get("metrics", {})
            lines.append(
                f"  {r['name']}: Return={m.get('annualized_return_pct','N/A')}%, "
                f"Sharpe={m.get('sharpe_ratio','N/A')}, Calmar={m.get('calmar_ratio','N/A')}, "
                f"MaxDD={m.get('max_drawdown_pct','N/A')}%, Vol={m.get('volatility_ann_pct','N/A')}%, "
                f"WinRate={m.get('win_rate_pct','N/A')}%, PF={m.get('profit_factor','N/A')}"
            )
        return "\n".join(lines)

    def _build_backtest_context(self, ticker: str) -> str:
        """Summarize backtest results for a given ticker."""
        if not self.backtest_results:
            return "No backtest data available."
        lines = []
        for r in self.backtest_results:
            m = r.get("metrics", {})
            bt_tickers = r.get("tickers", [])
            if ticker not in bt_tickers:
                continue
            lines.append(
                f"Strategy '{r['name']}': Sharpe={m.get('sharpe_ratio','N/A')}, "
                f"MaxDD={m.get('max_drawdown_pct','N/A')}%, "
                f"WinRate={m.get('win_rate_pct','N/A')}%, "
                f"ProfitFactor={m.get('profit_factor','N/A')}"
            )
        return "\n".join(lines) if lines else "No backtest data for this ticker."

    def trigger_backtest(self, strategy_indices: list | None = None,
                         config_path: str = "", verbose: bool = True) -> list:
        """Execute backtesting on strategies from strategy_config.json."""
        engine = BTEngine(config_path=config_path, verbose=verbose) if config_path else BTEngine(verbose=verbose)
        if strategy_indices is not None:
            results = engine.run_by_indices(strategy_indices)
        else:
            results = engine.run_all()
        strategies = StrategyConfig.load(config_path) if config_path else StrategyConfig.load()
        for r in results:
            for s in strategies:
                if s["name"] == r["name"]:
                    r["tickers"] = s.get("tickers", [])
                    break
        self.backtest_results = results
        self.last_backtest_date = datetime.today().strftime("%Y-%m-%d")
        return results

    def auto_backtest(self, target_date: str = "") -> list:
        """Full auto cycle: decide -> (if yes) trigger -> return results."""
        decision = self.decide_backtest(target_date)
        if not decision.get("should_backtest", False):
            print("  [TradingAgent] Backtest skipped --- conditions normal.")
            return []

        rec = decision.get("recommended_strategies", "all")
        if rec == "all" or not rec.strip():
            indices = None
        else:
            try:
                indices = [int(x.strip()) for x in rec.split(",") if x.strip().isdigit()]
            except (ValueError, AttributeError):
                indices = None

        print(f"  [TradingAgent] Triggering backtest (urgency={decision.get('urgency')})"
              f" --- strategies: {rec}")
        return self.trigger_backtest(indices)

    # --- best-strategy selection -------------------------------------------

    def select_best_strategy(self, config_path: str = "",
                             verbose: bool = True) -> dict:
        """Backtest all strategies and select the best by composite ranking."""
        results = self.trigger_backtest(config_path=config_path, verbose=verbose)
        if not results:
            raise ValueError("No valid backtest results. Check strategy config.")

        n = len(results)

        if n == 1:
            strategies = StrategyConfig.load(config_path) if config_path else StrategyConfig.load()
            idx = next((i for i, s in enumerate(strategies) if s["name"] == results[0]["name"]), 0)
            print(f"\n  Only 1 strategy available -> auto-selected: {results[0]['name']}")
            return {
                "index": idx, "name": results[0]["name"],
                "metrics": results[0]["metrics"], "score": 1.0,
                "strategy_config": strategies[idx],
            }

        ranking_metrics = [
            ("sharpe_ratio", True),
            ("calmar_ratio", True),
            ("sortino_ratio", True),
            ("profit_factor", True),
            ("max_drawdown_pct", False),
            ("win_rate_pct", True),
        ]

        ranks = {i: [] for i in range(n)}

        for metric, higher_better in ranking_metrics:
            values = []
            for r in results:
                v = r["metrics"].get(metric)
                if not isinstance(v, (int, float)) or v == float("inf") or v == float("-inf"):
                    v = float("-inf") if higher_better else float("inf")
                values.append(v)
            sorted_idx = sorted(range(n), key=lambda i: values[i], reverse=higher_better)
            for rank, idx in enumerate(sorted_idx):
                ranks[idx].append(rank + 1)

        avg_ranks = {i: np.mean(r) for i, r in ranks.items()}
        best_idx = int(min(avg_ranks, key=avg_ranks.get))

        max_r = max(avg_ranks.values())
        min_r = min(avg_ranks.values())
        score = 1.0 if max_r == min_r else round(1.0 - (avg_ranks[best_idx] - min_r) / (max_r - min_r), 3)

        strategies = StrategyConfig.load(config_path) if config_path else StrategyConfig.load()
        best_name = results[best_idx]["name"]
        config_idx = next((i for i, s in enumerate(strategies) if s["name"] == best_name), best_idx)

        if verbose:
            print(f"\n{'='*70}")
            print(f"  BEST STRATEGY RANKING (lower avg rank = better)")
            print(f"{'='*70}")
            print(f"  {'Rank':<6} {'Strategy':<22} {'AvgRank':>9} {'Score':>7} "
                  f"{'Sharpe':>8} {'Calmar':>8} {'MaxDD%':>8} {'PF':>7} {'Win%':>7}")
            print(f"  {'-'*6} {'-'*22} {'-'*9} {'-'*7} {'-'*8} {'-'*8} {'-'*8} {'-'*7} {'-'*7}")
            sorted_by_rank = sorted(avg_ranks.items(), key=lambda x: x[1])
            for rank_pos, (idx, avg_r) in enumerate(sorted_by_rank):
                r = results[idx]
                m = r["metrics"]
                marker = " *" if idx == best_idx else "  "
                pf = m["profit_factor"]
                pf_str = f"{pf:.2f}" if isinstance(pf, (int, float)) else str(pf)
                s = 1.0 if max_r == min_r else round(1.0 - (avg_r - min_r) / (max_r - min_r), 3)
                print(f"  {rank_pos+1:<6} {r['name']:<22} {avg_r:>8.3f} {s:>6.3f}{marker} "
                      f"{m['sharpe_ratio']:>8.3f} {m['calmar_ratio']:>8.3f} "
                      f"{m['max_drawdown_pct']:>7.2f}% {pf_str:>7} "
                      f"{m['win_rate_pct']:>6.2f}%")
            print(f"\n  * Selected: {results[best_idx]['name']} (score={score}, "
                  f"Sharpe={results[best_idx]['metrics']['sharpe_ratio']})")

        return {
            "index": config_idx, "name": best_name,
            "metrics": results[best_idx]["metrics"], "score": score,
            "strategy_config": strategies[config_idx],
        }

    def auto_select_and_trade(self, target_date: str = "",
                              dry_run: bool = True,
                              use_bracket: bool = False) -> dict:
        """Full auto pipeline: backtest all -> select best -> paper trade."""
        target_date = target_date or datetime.today().strftime("%Y-%m-%d")

        print(f"\n{'='*60}")
        print(f"  AUTO-SELECT BEST STRATEGY & TRADE | {target_date}")
        print(f"{'='*60}")

        print(f"\n  --- PHASE 1: BACKTEST ALL STRATEGIES ---")
        best = self.select_best_strategy(verbose=True)

        print(f"\n  --- PHASE 2: TRADE WITH BEST STRATEGY ---")
        print(f"  Best strategy : {best['name']} (score={best['score']})")
        print(f"  Order mode    : {'dry run' if dry_run else 'REAL ORDERS'}")
        if use_bracket:
            print(f"  TP/SL         : enabled (TP={settings.take_profit_pct*100:.0f}%, "
                  f"SL={settings.stop_loss_pct*100:.0f}%)")

        weights = self.run_with_strategy(
            best["index"], target_date=target_date, dry_run=dry_run
        )
        self.report()

        print(f"\n  AUTO-SELECT COMPLETE")
        print(f"  Traded with : {best['name']}")
        print(f"  Score       : {best['score']}")
        print(f"  Sharpe      : {best['metrics']['sharpe_ratio']}")
        print(f"  MaxDD       : {best['metrics']['max_drawdown_pct']}%")

        return weights

    # --- multi-strategy parallel trading -----------------------------------

    def run_multi_strategies(self, strategy_indices: list[int],
                             capital_weights: list[float] | None = None,
                             target_date: str = "",
                             dry_run: bool = True,
                             use_bracket: bool = False) -> dict:
        """Run multiple strategies in parallel and combine their target weights."""
        strategies = StrategyConfig.load()
        n = len(strategy_indices)
        if n == 0:
            raise ValueError("Need at least 1 strategy index.")
        for idx in strategy_indices:
            if idx < 0 or idx >= len(strategies):
                raise IndexError(f"Strategy index {idx} out of range (0-{len(strategies)-1})")

        if capital_weights is None:
            capital_weights = [1.0 / n] * n
        else:
            total = sum(capital_weights)
            capital_weights = [w / total for w in capital_weights]

        target_date = target_date or datetime.today().strftime("%Y-%m-%d")

        print(f"\n  MULTI-STRATEGY PARALLEL TRADING")
        print(f"  {n} strategies | {target_date} | "
              f"Capital: ${settings.initial_capital:,}")
        for i, idx in enumerate(strategy_indices):
            s = strategies[idx]
            name = s['name']
            n_factors = len(s.get('factors', {}))
            cap = capital_weights[i] * 100
            print(f"  [{i}] #{idx} {name:<22}  {n_factors:>2}f  | {cap:>5.1f}%")

        all_tickers = set()
        for idx in strategy_indices:
            s = strategies[idx]
            StrategyConfig.validate(s)
            all_tickers.update(s.get("tickers", []))
        all_tickers = sorted(all_tickers)

        self.raw_data = self.data_agent.fetch_market_data(
            all_tickers, settings.backtest_start, target_date
        )
        end_dt = pd.to_datetime(target_date)
        hist = self.raw_data[self.raw_data.index < end_dt].copy()

        print(f"\n  --- RUNNING {n} STRATEGIES IN PARALLEL ---")
        all_strategy_weights: list[dict[str, float]] = []
        all_strategy_names: list[str] = []
        for i, idx in enumerate(strategy_indices):
            s = strategies[idx]
            strategy_tickers = [t for t in s["tickers"] if t in hist.columns]
            strategy_name = s['name']
            all_strategy_names.append(strategy_name)
            ticker_prices = hist[strategy_tickers]
            benchmark = hist["SPY"] if "SPY" in hist.columns else hist.iloc[:, 0]

            print(f"\n  [{i}] {strategy_name}")
            signals = self._compute_strategy_signals(s, ticker_prices, benchmark)

            if signals:
                sorted_sigs = sorted(signals.items(), key=lambda x: -x[1])
                for t, score in sorted_sigs[:6]:
                    bar = "#" * max(1, int(abs(score) * 10))
                    direction = "+" if score > 0 else " "
                    print(f"    {t:<6} {direction}{score:+.3f} {bar}")

            saved_tickers = self.tickers
            self.tickers = strategy_tickers
            self._raw_strategy_scores = signals
            w = self._strategy_weights(s)
            self.tickers = saved_tickers
            all_strategy_weights.append(w)

        combined_weights: dict[str, float] = {}
        all_tickers_in_use = set()
        for w in all_strategy_weights:
            all_tickers_in_use.update(w.keys())
        all_tickers_in_use = sorted(all_tickers_in_use)

        contribution: dict[str, dict[str, float]] = {}
        for ticker in all_tickers_in_use:
            contribution[ticker] = {}
            combined = 0.0
            for i, w in enumerate(all_strategy_weights):
                contrib = w.get(ticker, 0.0) * capital_weights[i]
                contribution[ticker][all_strategy_names[i]] = contrib
                combined += contrib
            combined_weights[ticker] = combined

        total = sum(combined_weights.values())
        if total > 0:
            combined_weights = {t: w / total for t, w in combined_weights.items()}

        self.target_weights = combined_weights

        print(f"\n  --- WEIGHT CONTRIBUTION BREAKDOWN ---")
        for ticker, tw in sorted(combined_weights.items(), key=lambda x: -x[1]):
            if tw < 0.01:
                continue
            parts = "  ".join(f"{name}:{contribution[ticker].get(name,0)*100:.0f}%"
                            for name in all_strategy_names)
            print(f"  {ticker:<6} {parts}  -> {tw*100:.1f}%")

        print(f"\n  --- Final Combined Weights ---")
        for t, w in sorted(combined_weights.items(), key=lambda x: -x[1]):
            if w > 0.01:
                bar = "#" * int(w * 50)
                print(f"    {t:<6} {w*100:5.1f}% {bar}")

        print(f"\n  -- Risk (LLM) --")
        self.tickers = [t for t in all_tickers_in_use if t in hist.columns]
        bt_summary = self._build_backtest_summary()
        self.risk_assessment = self.risk_agent.assess(
            hist, self.tickers, target_date, bt_summary)
        print(f"  Level: {self.risk_assessment['risk_level']}  "
              f"Action: {self.risk_assessment['action']}")
        if self.risk_assessment.get("action") == "Liquidate All Long Positions":
            print(f"    Risk override: LIQUIDATE ALL")
            combined_weights = {t: 0.0 for t in self.tickers}
            self.target_weights = combined_weights

        if ALPACA_AVAILABLE:
            self.executor = AlpacaExecutor()
            self.executor.print_summary()
            self.executor.rebalance(combined_weights, dry_run=dry_run,
                                    use_bracket=use_bracket)
        else:
            print("  [TradingAgent] Alpaca unavailable --- skipping execution.")

        return combined_weights

    # --- report helpers ----------------------------------------------------

    def report(self):
        """Pretty-print the full pipeline result."""
        print("\n" + "=" * 60)
        if self.strategy_mode and self.active_strategy:
            print(f"  TRADING AGENT REPORT (Strategy: {self.active_strategy['name']})")
        else:
            print("  TRADING AGENT REPORT")
        print("=" * 60)
        if self.strategy_mode and self.active_strategy:
            s = self.active_strategy
            print(f"\nStrategy Config:")
            print(f"  Name: {s['name']}")
            print(f"  Factors: {len(s.get('factors',{}))} | Logic: {s.get('signal_logic','N/A')}")
            active_factors = list(s.get('factors', {}).keys())
            print(f"  Active factors: {', '.join(active_factors[:8])}"
                  f"{'...' if len(active_factors) > 8 else ''}")
        print(f"\nMarket State:")
        print(json.dumps(self.market_state, indent=2) if self.market_state else "  (not assessed in strategy mode)")
        print(f"\nStock Signals:")
        for t, s in self.stock_signals.items():
            print(f"  {t:<6} {s.get('signal','?'):<5}  {s.get('reasoning','')}")
        print(f"\nRisk Assessment:")
        print(json.dumps(self.risk_assessment, indent=2) if self.risk_assessment else "  (not assessed)")
        if self.frequency_decision:
            fd = self.frequency_decision
            print(f"\nRebalance Frequency (LLM):")
            print(f"  Recommended: {fd.get('recommended_frequency','?')}  "
                  f"Confidence: {fd.get('confidence',0):.2f}")
            print(f"  Reasoning: {fd.get('reasoning','')}")
        print(f"\nFinal Weights:")
        for t, w in sorted(self.target_weights.items(), key=lambda x: -x[1]):
            print(f"  {t:<6} {w*100:5.1f}%")
