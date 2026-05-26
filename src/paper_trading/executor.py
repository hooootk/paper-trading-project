"""AlpacaExecutor --- paper trade execution via Alpaca API."""

import time

import numpy as np
import yfinance as yf

from paper_trading.config import settings

ALPACA_AVAILABLE = False
BRACKET_SUPPORT = False
MarketOrderRequest = None
LimitOrderRequest = None
StopOrderRequest = None
TradingClient = None
GetOrdersRequest = None
OrderSide = None
TimeInForce = None
OrderClass = None
TakeProfitRequest = None
StopLossRequest = None

try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest, StopOrderRequest, GetOrdersRequest
    from alpaca.trading.enums import OrderSide, TimeInForce
    ALPACA_AVAILABLE = True
    try:
        from alpaca.trading.enums import OrderClass
        from alpaca.trading.requests import TakeProfitRequest, StopLossRequest
        BRACKET_SUPPORT = True
    except ImportError:
        OrderClass = None  # type: ignore
        TakeProfitRequest = None  # type: ignore
        StopLossRequest = None  # type: ignore
        BRACKET_SUPPORT = False
except ImportError:
    ALPACA_AVAILABLE = False
    BRACKET_SUPPORT = False
    print("alpaca-py not installed. Run: pip install alpaca-py")


class AlpacaExecutor:
    """Wrapper around the Alpaca paper-trading API with TP/SL support."""

    def __init__(self):
        if not ALPACA_AVAILABLE:
            raise RuntimeError("alpaca-py not installed.")
        self.client = TradingClient(settings.alpaca_api_key, settings.alpaca_secret_key, paper=True)
        account = self.client.get_account()
        print(f"  [AlpacaExecutor] Connected --- Equity: ${float(account.equity):,.2f}")

    def summary(self) -> dict:
        account = self.client.get_account()
        positions = self.client.get_all_positions()
        return {
            "cash": float(account.cash),
            "portfolio_value": float(account.portfolio_value),
            "equity": float(account.equity),
            "buying_power": float(account.buying_power),
            "positions": {p.symbol: {"qty": float(p.qty), "market_value": float(p.market_value),
                                     "unrealized_pl": float(p.unrealized_pl)} for p in positions},
        }

    def print_summary(self):
        info = self.summary()
        print("\n-- Alpaca Account --------------------------------------------------")
        print(f"  Cash           : ${info['cash']:>12,.2f}")
        print(f"  Portfolio Value: ${info['portfolio_value']:>12,.2f}")
        print(f"  Equity         : ${info['equity']:>12,.2f}")
        print(f"  Buying Power   : ${info['buying_power']:>12,.2f}")
        print(f"  Positions ({len(info['positions'])}):")
        for sym, p in info['positions'].items():
            print(f"    {sym:<6} qty={p['qty']:>6.0f}  value=${p['market_value']:>10,.2f}"
                  f"  P&L=${p['unrealized_pl']:>+8,.2f}")
        return info

    def rebalance(self, target_weights: dict, dry_run: bool = True,
                  use_bracket: bool = False,
                  tp_pct: float | None = None,
                  sl_pct: float | None = None) -> list:
        """Align the paper portfolio to target_weights."""
        if tp_pct is None:
            tp_pct = settings.take_profit_pct
        if sl_pct is None:
            sl_pct = settings.stop_loss_pct

        account = self.client.get_account()
        equity = float(account.equity)
        buying_power = float(account.buying_power)
        positions = {p.symbol: float(p.qty) for p in self.client.get_all_positions()}

        tickers = list(target_weights.keys())
        prices = yf.download(tickers, period="2d", progress=False)["Close"].iloc[-1].to_dict()

        order_label = "bracket" if use_bracket else "market"
        print(f"\n-- Rebalancing (equity=${equity:,.2f}, buying_power=${buying_power:,.2f}, "
              f"dry_run={dry_run}, {order_label}) --")

        sells = []
        buys = []
        total_sell_proceeds = 0.0

        for ticker, weight in target_weights.items():
            if ticker not in prices or np.isnan(prices[ticker]):
                print(f"  {ticker}  no price -> skip")
                continue
            price = prices[ticker]
            target_qty = int(equity * weight / price)
            current_qty = int(positions.get(ticker, 0))
            delta = target_qty - current_qty
            if delta == 0:
                print(f"  {ticker:<6}  no change  (qty={current_qty})")
                continue
            if delta > 0:
                buys.append((ticker, delta, price, delta * price))
            else:
                qty = abs(delta)
                sells.append((ticker, qty, price, qty * price))
                total_sell_proceeds += qty * price

        submitted = []

        if dry_run:
            for ticker, qty, price, cost in sells:
                print(f"  {ticker:<6}  SELL {qty:>4} @ ~${price:.2f}  ~${cost:,.2f}")
            for ticker, qty, price, cost in buys:
                tp_str = f" TP={tp_pct*100:.0f}%" if use_bracket else ""
                sl_str = f" SL={sl_pct*100:.0f}%" if use_bracket else ""
                print(f"  {ticker:<6}  BUY {qty:>4} @ ~${price:.2f}  ~${cost:,.2f}{tp_str}{sl_str}")
            print(f"  -> Dry run (no orders).")
            return submitted

        if sells:
            print(f"  -- Submitting {len(sells)} sell(s) --")
        for ticker, qty, price, cost in sells:
            print(f"  {ticker:<6}  SELL {qty:>4} @ ~${price:.2f}  ~${cost:,.2f}")
            try:
                existing = self.client.get_orders(
                    GetOrdersRequest(status="open", symbols=[ticker], limit=50)
                )
                for o in existing:
                    self.client.cancel_order_by_id(str(o.id))
                    print(f"    Cancelled open order {o.id} for {ticker}")
                if existing:
                    time.sleep(0.3)
                order = MarketOrderRequest(
                    symbol=ticker, qty=qty, side=OrderSide.SELL,
                    time_in_force=TimeInForce.DAY,
                )
                self.client.submit_order(order)
                submitted.append(ticker)
            except Exception as e:
                print(f"    Sell order failed: {e}")

        if buys:
            if sells:
                print(f"  Waiting 3s for sells to settle ...")
                time.sleep(3)
                account = self.client.get_account()
                buying_power = float(account.buying_power)
                print(f"  -- Submitting {len(buys)} buy(s) (buying_power=${buying_power:,.2f}) --")
            else:
                print(f"  -- Submitting {len(buys)} buy(s) (buying_power=${buying_power:,.2f}) --")

            buys.sort(key=lambda x: -x[3])
            remaining_bp = buying_power

            for ticker, qty, price, cost in buys:
                scaled = False
                if cost > remaining_bp:
                    new_qty = int(remaining_bp / price) if price > 0 else 0
                    if new_qty <= 0:
                        print(f"  {ticker:<6}  BUY   skip --- ${cost:,.2f} > remaining ${remaining_bp:,.2f}")
                        continue
                    qty = new_qty
                    cost = qty * price
                    scaled = True

                tp_str = f" TP={tp_pct*100:.0f}%" if use_bracket else ""
                sl_str = f" SL={sl_pct*100:.0f}%" if use_bracket else ""
                note = " (scaled to fit BP)" if scaled else ""
                print(f"  {ticker:<6}  BUY {qty:>4} @ ~${price:.2f}  ~${cost:,.2f}{tp_str}{sl_str}{note}")
                try:
                    if use_bracket and qty > 0:
                        self._submit_bracket_order(ticker, qty, price, tp_pct, sl_pct)
                    else:
                        order = MarketOrderRequest(
                            symbol=ticker, qty=qty, side=OrderSide.BUY,
                            time_in_force=TimeInForce.DAY,
                        )
                        self.client.submit_order(order)
                    submitted.append(ticker)
                    remaining_bp -= cost
                except Exception as e:
                    print(f"    Buy order failed: {e}")

        print(f"  -> {len(submitted)} order(s) submitted.")
        return submitted

    def _submit_bracket_order(self, ticker: str, qty: int, price: float,
                              tp_pct: float, sl_pct: float):
        """Submit a bracket order: market buy + take-profit limit + stop-loss stop."""
        tp_price = round(price * (1 + tp_pct), 2)
        sl_price = round(price * (1 - sl_pct), 2)

        if BRACKET_SUPPORT:
            take_profit = TakeProfitRequest(limit_price=tp_price)
            stop_loss = StopLossRequest(stop_price=sl_price)
            bracket_order = MarketOrderRequest(
                symbol=ticker, qty=qty, side=OrderSide.BUY,
                time_in_force=TimeInForce.DAY,
                order_class=OrderClass.BRACKET,
                take_profit=take_profit,
                stop_loss=stop_loss,
            )
            self.client.submit_order(bracket_order)
            print(f"    Bracket: buy {qty} {ticker} | TP @ ${tp_price} | SL @ ${sl_price}")
        else:
            buy_order = MarketOrderRequest(
                symbol=ticker, qty=qty, side=OrderSide.BUY,
                time_in_force=TimeInForce.DAY,
            )
            self.client.submit_order(buy_order)
            tp_order = LimitOrderRequest(
                symbol=ticker, qty=qty, side=OrderSide.SELL,
                limit_price=tp_price, time_in_force=TimeInForce.GTC,
            )
            sl_order = StopOrderRequest(
                symbol=ticker, qty=qty, side=OrderSide.SELL,
                stop_price=sl_price, time_in_force=TimeInForce.GTC,
            )
            self.client.submit_order(tp_order)
            self.client.submit_order(sl_order)
            print(f"    Buy + TP/SL (fallback): {qty} {ticker} | TP @ ${tp_price} | SL @ ${sl_price}")

    def attach_tpsl_all(self, tp_pct: float | None = None,
                        sl_pct: float | None = None,
                        dry_run: bool = True) -> list:
        """Attach TP/SL (OCO) orders to all positions that lack them."""
        if tp_pct is None:
            tp_pct = settings.take_profit_pct
        if sl_pct is None:
            sl_pct = settings.stop_loss_pct

        positions = self.client.get_all_positions()
        if not positions:
            print("  No open positions.")
            return []
        print(f"\n-- Attaching TP/SL to {len(positions)} position(s) "
              f"(TP={tp_pct*100:.0f}%, SL={sl_pct*100:.0f}%, dry_run={dry_run}) --")
        tickers = [p.symbol for p in positions]
        prices = yf.download(tickers, period="2d", progress=False)["Close"].iloc[-1].to_dict()
        attached = []
        for pos in positions:
            sym = pos.symbol
            qty = int(float(pos.qty))
            if qty <= 0 or sym not in prices:
                continue
            price = prices[sym]
            cost_basis = float(pos.avg_entry_price) if hasattr(pos, 'avg_entry_price') and float(pos.avg_entry_price) > 0 else price

            tp_price = round(cost_basis * (1 + tp_pct), 2)
            sl_price = round(cost_basis * (1 - sl_pct), 2)
            print(f"  {sym:<6} qty={qty}  cost=${cost_basis:.2f}  "
                  f"TP=${tp_price:.2f} ({tp_pct*100:.0f}%)  SL=${sl_price:.2f} ({sl_pct*100:.0f}%)")
            if not dry_run:
                try:
                    existing = self.client.get_orders(
                        GetOrdersRequest(status="open", symbols=[sym], limit=50)
                    )
                    for o in existing:
                        self.client.cancel_order_by_id(str(o.id))
                        print(f"    Cancelled existing order: {o.id}")
                    if existing:
                        time.sleep(0.3)
                    tp_order = LimitOrderRequest(
                        symbol=sym, qty=qty, side=OrderSide.SELL,
                        limit_price=tp_price, time_in_force=TimeInForce.GTC,
                    )
                    sl_order = StopOrderRequest(
                        symbol=sym, qty=qty, side=OrderSide.SELL,
                        stop_price=sl_price, time_in_force=TimeInForce.GTC,
                    )
                    self.client.submit_order(tp_order)
                    self.client.submit_order(sl_order)
                    print(f"    TP+SL submitted")
                    attached.append(sym)
                except Exception as e:
                    print(f"    Failed: {e}")
        print(f"  -> {'Dry run.' if dry_run else f'{len(attached)} position(s) protected.'}")
        return attached

    def check_tpsl_status(self):
        """Report P&L vs TP/SL thresholds for current positions."""
        info = self.summary()
        positions = info["positions"]
        if not positions:
            print("  No open positions.")
            return
        tp = settings.take_profit_pct
        sl = settings.stop_loss_pct
        print(f"\n-- TP/SL Status Check (TP={tp*100:.0f}%, SL={sl*100:.0f}%) --")
        for sym, p in positions.items():
            pl_pct = (p["unrealized_pl"] / (p["market_value"] - p["unrealized_pl"])) * 100 if p["market_value"] != p["unrealized_pl"] else 0
            status = "O OK"
            if pl_pct >= tp * 100:
                status = "* TP HIT"
            elif pl_pct <= -sl * 100:
                status = "v SL HIT"
            elif pl_pct >= tp * 80:
                status = "^ Near TP"
            elif pl_pct <= -sl * 80:
                status = "v Near SL"
            print(f"  {sym:<6} P&L={pl_pct:+.2f}%  {status}  (value=${p['market_value']:,.2f})")
