"""Interactive CLI menu and command-line argument parsing."""

import sys
from datetime import datetime

import numpy as np
import pandas as pd

from paper_trading.backtest_engine import StrategyConfig
from paper_trading.config import settings
from paper_trading.executor import ALPACA_AVAILABLE, AlpacaExecutor
from paper_trading.trading_agent import TradingAgent
from paper_trading.intent import recognize_intent, OPTION_LABELS

# ---------------------------------------------------------------------------
# Menu display
# ---------------------------------------------------------------------------

def _show_menu():
    """Display the interactive menu."""
    print(r"""
╔══════════════════════════════════════════════════╗
║              PAPER TRADING AGENT                 ║
╠══════════════════════════════════════════════════╣
║                                                  ║
║  [1]  LLM Multi-Agent Trading (Dry Run)          ║
║  [2]  LLM Multi-Agent Trading (Real Orders)      ║
║  [3]  Strategy-Based Trading (Dry Run)           ║
║  [4]  Strategy-Based Trading (Real Orders)       ║
║  [5]  Backtest All Strategies                    ║
║  [6]  Backtest Single Strategy                   ║
║  [7]  Live Trading + Auto Backtest               ║
║  [8]  Regenerate Strategy Config                 ║
║  [9]  View Alpaca Account Summary                ║
║  [10] LLM Rebalance Frequency Analysis           ║
║  [11] Multi-Strategy Parallel Trading            ║
║  [12] Manage TP/SL (Attach + Status Check)       ║
║  [13] Auto-Select Best Strategy & Trade          ║
║  [14] Natural Language Input (AI Intent Recog.)  ║
║  [0]  Exit                                       ║
║                                                  ║
╚══════════════════════════════════════════════════╝
""")


def _list_strategies():
    """Print available strategies from strategy_config.json."""
    try:
        strategies = StrategyConfig.load()
    except Exception as e:
        print(f"  Failed to load strategy config: {e}")
        return []
    if not strategies:
        print("  No strategies found. Run [8] to generate config first.")
        return []
    print(f"\n  Available strategies ({len(strategies)}):")
    for i, s in enumerate(strategies):
        factors = list(s.get("factors", {}).keys())
        tickers = s.get("tickers", [])
        print(f"    [{i}] {s['name']}")
        print(f"        Tickers: {', '.join(tickers[:6])}"
              f"{'...' if len(tickers) > 6 else ''}")
        print(f"        Factors: {len(factors)} | "
              f"Logic: {s.get('signal_logic','?')} | "
              f"Sizing: {s.get('position_sizing','?')}")
    print()
    return strategies


def _pick_strategy(strategies: list) -> int | None:
    """Prompt user to pick a strategy index. Returns index or None."""
    if not strategies:
        return None
    while True:
        try:
            raw = input(f"  Select strategy index [0-{len(strategies)-1}]: ").strip()
            if raw == "":
                return None
            idx = int(raw)
            if 0 <= idx < len(strategies):
                return idx
            print(f"  Invalid index. Choose 0-{len(strategies)-1}.")
        except (ValueError, EOFError, KeyboardInterrupt):
            return None


def _view_account_summary():
    """Print Alpaca paper account summary."""
    if not ALPACA_AVAILABLE:
        print("  alpaca-py not installed. Run: pip install alpaca-py")
        return
    try:
        executor = AlpacaExecutor()
        executor.print_summary()
    except Exception as e:
        print(f"  Failed to fetch account summary: {e}")


# ---------------------------------------------------------------------------
# Option dispatcher
# ---------------------------------------------------------------------------

def execute_option(choice: str, target_date: str) -> str:
    """Execute a single menu option. Returns 'continue', 'exit', or 'invalid'."""
    if choice == "0":
        print("  Goodbye.")
        return "exit"

    elif choice == "1":
        print(f"\n  -- LLM Multi-Agent Trading (Dry Run) | {target_date} --\n")
        agent = TradingAgent()
        agent.run(target_date=target_date, dry_run=True)
        agent.report()
        return "continue"

    elif choice == "2":
        confirm = input("  Submit REAL orders to Alpaca paper account? [y/N]: ").strip().lower()
        if confirm != "y":
            print("  Cancelled.")
        else:
            print(f"\n  -- LLM Multi-Agent Trading (Real Orders) | {target_date} --\n")
            agent = TradingAgent()
            agent.run(target_date=target_date, dry_run=False)
            agent.report()
        return "continue"

    elif choice == "3":
        strategies = _list_strategies()
        idx = _pick_strategy(strategies)
        if idx is None:
            print("  Cancelled.")
        else:
            print(f"\n  -- Strategy-Based Trading (Dry Run) | #{idx} | {target_date} --\n")
            agent = TradingAgent()
            agent.run_with_strategy(idx, target_date=target_date, dry_run=True)
            agent.report()
        return "continue"

    elif choice == "4":
        strategies = _list_strategies()
        idx = _pick_strategy(strategies)
        if idx is None:
            print("  Cancelled.")
        else:
            confirm = input("  Submit REAL orders to Alpaca paper account? [y/N]: ").strip().lower()
            if confirm != "y":
                print("  Cancelled.")
            else:
                print(f"\n  -- Strategy-Based Trading (Real Orders) | #{idx} | {target_date} --\n")
                agent = TradingAgent()
                agent.run_with_strategy(idx, target_date=target_date, dry_run=False)
                agent.report()
        return "continue"

    elif choice == "5":
        print(f"\n  -- Backtest All Strategies --\n")
        agent = TradingAgent()
        agent.trigger_backtest(verbose=True)
        return "continue"

    elif choice == "6":
        strategies = _list_strategies()
        idx = _pick_strategy(strategies)
        if idx is None:
            print("  Cancelled.")
        else:
            print(f"\n  -- Backtest Strategy [{idx}] --\n")
            agent = TradingAgent()
            agent.trigger_backtest([idx], verbose=True)
        return "continue"

    elif choice == "7":
        print(f"\n  -- Live Trading + Auto Backtest | {target_date} --\n")
        agent = TradingAgent()
        agent.run(target_date=target_date, dry_run=True)
        agent.report()
        print(f"\n  -- Auto Backtest Decision --")
        results = agent.auto_backtest(target_date)
        if results:
            print(f"\n  {len(results)} strategy(s) backtested.")
        return "continue"

    elif choice == "8":
        try:
            n = input("  Number of strategies to generate [5]: ").strip()
            n = int(n) if n else 5
        except (ValueError, EOFError, KeyboardInterrupt):
            n = 5
        print(f"\n  -- Generating {n} strategies --\n")
        StrategyConfig.generate_full_config(num_strategies=n)
        print("  Done.")
        return "continue"

    elif choice == "9":
        _view_account_summary()
        return "continue"

    elif choice == "10":
        print(f"\n  -- Rebalance Frequency Analysis | {target_date} --\n")
        agent = TradingAgent()
        agent.raw_data = agent.data_agent.fetch_market_data(
            agent.tickers, settings.backtest_start, target_date
        )
        end_dt = pd.to_datetime(target_date)
        hist = agent.raw_data[agent.raw_data.index < end_dt].copy()
        print(f"  -- Macro --")
        agent.market_state = agent.macro_agent.assess(hist, target_date)
        print(f"  Phase: {agent.market_state['market_phase']}  "
              f"Appetite: {agent.market_state['risk_appetite']}/10")
        print(f"  -- Risk --")
        bt_summary = agent._build_backtest_summary()
        agent.risk_assessment = agent.risk_agent.assess(hist, agent.tickers, target_date, bt_summary)
        print(f"  Level: {agent.risk_assessment['risk_level']}  "
              f"Action: {agent.risk_assessment['action']}")
        print(f"  -- Frequency Decision --")
        agent.decide_rebalance_frequency(target_date)
        return "continue"

    elif choice == "11":
        strategies = _list_strategies()
        if not strategies:
            return "continue"
        print("  Multi-Strategy: select 2+ strategies to run in parallel.")
        raw = input("  Strategy indices (comma-separated, e.g. 0,1,2): ").strip()
        if not raw:
            print("  Cancelled.")
            return "continue"
        try:
            indices = [int(x.strip()) for x in raw.split(",") if x.strip()]
        except ValueError:
            print("  Invalid indices.")
            return "continue"
        if len(indices) < 2:
            print("  Multi-strategy needs at least 2 strategies.")
            return "continue"
        for j, idx in enumerate(indices):
            s = strategies[idx]
            print(f"  [{j}] #{idx} {s['name']}")

        custom_cap = input("  Custom weights (e.g. 50,30,20) or Enter for equal: ").strip()
        cap_weights = None
        if custom_cap:
            try:
                cap_weights = [float(x.strip()) for x in custom_cap.split(",") if x.strip()]
                if len(cap_weights) != len(indices):
                    print(f"  Need {len(indices)} weights, got {len(cap_weights)}. Using equal split.")
                    cap_weights = None
                else:
                    total = sum(cap_weights)
                    cap_weights = [w / total for w in cap_weights]
            except ValueError:
                print("  Invalid weights. Using equal split.")
                cap_weights = None

        confirm = input("  Submit REAL orders to Alpaca paper account? [y/N]: ").strip().lower()
        dry = confirm != "y"
        use_bracket = input("  Use bracket orders with TP/SL for buys? [y/N]: ").strip().lower() == "y"
        agent = TradingAgent()
        agent.run_multi_strategies(indices, target_date=target_date,
                                   dry_run=dry, use_bracket=use_bracket,
                                   capital_weights=cap_weights)
        return "continue"

    elif choice == "12":
        if not ALPACA_AVAILABLE:
            print("  alpaca-py not installed.")
        else:
            print(f"\n  -- TP/SL Management --")
            tp = input(f"  Take-Profit % [{settings.take_profit_pct*100:.0f}]: ").strip()
            sl = input(f"  Stop-Loss % [{settings.stop_loss_pct*100:.0f}]: ").strip()
            tp_pct = float(tp) / 100 if tp else settings.take_profit_pct
            sl_pct = float(sl) / 100 if sl else settings.stop_loss_pct
            execute = input("  Submit TP/SL orders? [y/N]: ").strip().lower() == "y"
            executor = AlpacaExecutor()
            executor.check_tpsl_status()
            executor.attach_tpsl_all(tp_pct=tp_pct, sl_pct=sl_pct, dry_run=not execute)
        return "continue"

    elif choice == "13":
        print(f"\n  -- Auto-Select Best Strategy & Trade | {target_date} --\n")
        confirm = input("  Submit REAL orders to Alpaca paper account? [y/N]: ").strip().lower()
        dry = confirm != "y"
        use_bracket = False
        if not dry:
            use_bracket = input("  Use bracket orders with TP/SL for buys? [y/N]: ").strip().lower() == "y"
        agent = TradingAgent()
        try:
            agent.auto_select_and_trade(target_date=target_date,
                                        dry_run=dry, use_bracket=use_bracket)
        except ValueError as e:
            print(f"  Error: {e}")
        return "continue"

    elif choice == "14":
        print(f"\n  -- Natural Language Input (AI Intent Recognition) --")
        print("  Describe what you want to do in plain English or Chinese.")
        try:
            user_text = input("  Your request: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("  Cancelled.")
            return "continue"
        if not user_text:
            print("  Cancelled.")
            return "continue"

        print(f"  Recognizing intent for: \"{user_text}\"")
        intent = recognize_intent(user_text)
        matched = intent.get("matched_options", [])
        confidence = intent.get("confidence", 0.0)
        reasoning = intent.get("reasoning", "")

        print(f"  Reasoning: {reasoning}")
        print(f"  Confidence: {confidence:.2f}")

        if not matched:
            print(f"\n  X Unable to match any existing function.")
            print(f"  Available functions:")
            for num, label in OPTION_LABELS.items():
                print(f"    [{num}] {label}")
            return "continue"

        if len(matched) == 1:
            opt = matched[0]
            label = OPTION_LABELS.get(opt, f"Option {opt}")
            print(f"\n  v Matched: [{opt}] {label}")
            if confidence >= 0.7:
                confirm = input(f"  Execute this function? [Y/n]: ").strip().lower()
                if confirm in ("n", "no"):
                    print("  Cancelled.")
                    return "continue"
            else:
                confirm = input(f"  Low confidence. Execute anyway? [y/N]: ").strip().lower()
                if confirm != "y":
                    print("  Cancelled.")
                    return "continue"
            print(f"  -> Executing [{opt}] {label}\n")
            return execute_option(str(opt), target_date)

        print(f"\n  ! Matched {len(matched)} possible functions:")
        for i, opt in enumerate(matched):
            label = OPTION_LABELS.get(opt, f"Option {opt}")
            print(f"    [{i+1}] [{opt}] {label}")
        print(f"    [0] Cancel")
        try:
            pick = input(f"  Select (1-{len(matched)}): ").strip()
            if pick == "0" or not pick:
                print("  Cancelled.")
                return "continue"
            pick_idx = int(pick) - 1
            if 0 <= pick_idx < len(matched):
                opt = matched[pick_idx]
                label = OPTION_LABELS.get(opt, f"Option {opt}")
                print(f"  -> Executing [{opt}] {label}\n")
                return execute_option(str(opt), target_date)
            else:
                print("  Invalid selection.")
        except (ValueError, EOFError, KeyboardInterrupt):
            print("  Cancelled.")
        return "continue"

    else:
        return "invalid"


# ---------------------------------------------------------------------------
# Interactive loop
# ---------------------------------------------------------------------------

def interactive_loop():
    """Run the interactive CLI menu loop."""
    target_date = datetime.today().strftime("%Y-%m-%d")

    while True:
        _show_menu()
        try:
            choice = input("  Select an option [0-14]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  Goodbye.")
            break

        status = execute_option(choice, target_date)
        if status == "exit":
            break
        elif status == "invalid":
            print(f"  Invalid option. Choose 0-14.")


# ---------------------------------------------------------------------------
# CLI entry point (argparse)
# ---------------------------------------------------------------------------

def main_cli():
    """Parse command-line arguments and dispatch."""
    if len(sys.argv) == 1:
        interactive_loop()
        sys.exit(0)

    import argparse

    parser = argparse.ArgumentParser(
        description="Paper Trading Agent --- Live trading + Backtesting orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m paper_trading                                      # interactive menu
  python -m paper_trading --live                               # LLM live trading (real orders)
  python -m paper_trading --use-strategy 2                     # strategy #2 rule-based (dry run)
  python -m paper_trading --backtest                           # backtest all strategies
  python -m paper_trading --backtest --strategy 0              # backtest strategy #0 only
  python -m paper_trading --auto-select                        # backtest all, select best, dry run
  python -m paper_trading --generate-config                    # regenerate strategy_config.json
  python -m paper_trading --summary                            # view Alpaca account summary
        """,
    )

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--live", action="store_true",
                      help="Live trading with real Alpaca orders")
    mode.add_argument("--dry-run", action="store_true",
                      help="Live trading pipeline without submitting orders (default)")
    mode.add_argument("--backtest", action="store_true",
                      help="Run backtesting only (no live trading)")
    mode.add_argument("--auto-backtest", action="store_true",
                      help="Live trading + agent decides whether to run backtests")
    mode.add_argument("--generate-config", action="store_true",
                      help="Regenerate strategy_config.json and exit")
    mode.add_argument("--summary", action="store_true",
                      help="View Alpaca paper account summary and exit")

    parser.add_argument("--strategy", type=int, default=None,
                        help="For --backtest: run a single strategy by index (0-based)")
    parser.add_argument("--use-strategy", type=int, default=None,
                        help="Use strategy_config.json[N] as the trading rules")
    parser.add_argument("--auto-select", action="store_true",
                        help="Backtest all strategies, auto-select the best, and paper trade")
    parser.add_argument("--strategies", type=int, default=5,
                        help="Number of strategies when generating config")
    parser.add_argument("--tickers", type=str, default=None,
                        help="Comma-separated ticker list override")
    parser.add_argument("--date", type=str, default="",
                        help="Target date YYYY-MM-DD (default: today)")
    parser.add_argument("--quiet", action="store_true",
                        help="Suppress verbose output")

    args = parser.parse_args()

    if args.summary:
        _view_account_summary()
        sys.exit(0)

    if args.generate_config:
        StrategyConfig.generate_full_config(num_strategies=args.strategies)
        print("Done. Run with --backtest to execute.")
        sys.exit(0)

    tickers = None
    if args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]

    agent = TradingAgent(tickers=tickers)
    target_date = args.date or datetime.today().strftime("%Y-%m-%d")

    if args.backtest:
        print(f"\n{'='*60}")
        print(f"  BACKTEST-ONLY MODE")
        print(f"{'='*60}")
        if args.strategy is not None:
            agent.trigger_backtest([args.strategy], verbose=not args.quiet)
        else:
            agent.trigger_backtest(verbose=not args.quiet)
        sys.exit(0)

    if args.auto_backtest:
        print(f"\n{'='*60}")
        print(f"  LIVE TRADING + AUTO BACKTEST")
        print(f"{'='*60}")
        if args.use_strategy is not None:
            agent.run_with_strategy(args.use_strategy, target_date=target_date, dry_run=True)
        else:
            agent.run(target_date=target_date, dry_run=True)
        agent.report()
        print(f"\n{'='*60}")
        print(f"  AUTO BACKTEST DECISION")
        print(f"{'='*60}")
        results = agent.auto_backtest(target_date)
        if results:
            print(f"\n  {len(results)} strategy(s) backtested.")
        sys.exit(0)

    dry_run = not args.live
    use_strat = args.use_strategy
    auto_select = args.auto_select

    if auto_select:
        print(f"\n{'='*60}")
        print(f"  LIVE TRADING --- AUTO-SELECT BEST STRATEGY")
        print(f"{'='*60}")
        agent.auto_select_and_trade(target_date=target_date, dry_run=dry_run)
        sys.exit(0)

    if use_strat is not None:
        mode_label = f"STRATEGY #{use_strat} RULE-BASED"
    else:
        mode_label = "LLM MULTI-AGENT"

    order_label = "real orders" if not dry_run else "dry run"
    print(f"\n{'='*60}")
    print(f"  LIVE TRADING --- {mode_label} ({order_label})")
    print(f"{'='*60}")

    if use_strat is not None:
        agent.run_with_strategy(use_strat, target_date=target_date, dry_run=dry_run)
    else:
        agent.run(target_date=target_date, dry_run=dry_run)
    agent.report()
