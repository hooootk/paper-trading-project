"""DataAgent --- fetches market data & computes technical indicators."""

import numpy as np
import pandas as pd
import yfinance as yf

from paper_trading.agents.base import BaseAgent
from paper_trading.config import settings


class DataAgent(BaseAgent):
    """Fetches price data and produces technical features for any ticker."""

    def __init__(self):
        super().__init__(
            name="DataAgent",
            system_prompt="You are a data assistant. Return JSON only.",
        )

    def fetch_market_data(self, tickers: list, start: str, end: str, extra_days: int = 730) -> pd.DataFrame:
        all_symbols = list(set(tickers + ["SPY", "^VIX"]))
        fetch_start = (pd.to_datetime(start) - pd.Timedelta(days=extra_days)).strftime("%Y-%m-%d")
        print(f"  [DataAgent] Downloading {len(all_symbols)} symbols {fetch_start} -> {end} ...")
        raw = yf.download(all_symbols, start=fetch_start, end=end, progress=False)["Close"]
        raw = raw.ffill()
        missing = [t for t in all_symbols if t not in raw.columns]
        if missing:
            raise ValueError(f"Missing data for: {missing}")
        print(f"  [DataAgent] {len(raw)} trading days x {len(raw.columns)} symbols.")
        return raw

    def technical_features(self, prices: pd.Series) -> dict:
        """Compute 15 technical indicators (past data only).

        These mirror the factor categories used by the BacktestEngine (24 factors)
        but kept lean (15 indicators) for LLM token efficiency.
        """
        lookback = settings.lookback_days
        recent = prices.tail(max(lookback, 120))
        current = recent.iloc[-1]
        n = len(recent)

        # --- Moving averages ---
        sma20 = recent.tail(20).mean()
        sma50 = recent.tail(50).mean() if n >= 50 else np.nan
        ema12 = recent.ewm(span=12, adjust=False).mean().iloc[-1]
        ema26 = recent.ewm(span=26, adjust=False).mean().iloc[-1]

        # --- RSI ---
        delta = recent.diff().dropna()
        gains = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean().iloc[-1]
        losses = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean().iloc[-1]
        rsi = 100 - (100 / (1 + gains / losses)) if losses != 0 else 100.0

        # --- MACD ---
        ema12_series = recent.ewm(span=12, adjust=False).mean()
        ema26_series = recent.ewm(span=26, adjust=False).mean()
        macd_series = ema12_series - ema26_series
        macd_signal_val = macd_series.ewm(span=9, adjust=False).mean().iloc[-1]
        macd_hist = macd_series.iloc[-1] - macd_signal_val

        # --- Bollinger Bands ---
        bb_std = recent.tail(20).std()
        bb_upper = sma20 + 2 * bb_std
        bb_lower = sma20 - 2 * bb_std
        bb_position = (current - sma20) / (2 * bb_std) if bb_std > 0 else 0

        # --- ATR (14) ---
        tr = pd.DataFrame({
            "hl": recent.diff().abs(),
            "hc": (recent - recent.shift(1)).abs(),
            "lc": (recent - recent.shift(1)).abs(),
        }).max(axis=1)
        atr = tr.tail(14).mean()

        # --- Stochastic %K (14,3) ---
        low14 = recent.tail(14).min()
        high14 = recent.tail(14).max()
        stoch_k = 100 * (current - low14) / (high14 - low14) if high14 != low14 else 50

        # --- Returns & momentum ---
        ret_5d = (current / recent.iloc[-5] - 1) * 100 if n >= 5 else np.nan
        ret_20d = (current / recent.iloc[-20] - 1) * 100 if n >= 20 else np.nan
        ret_60d = (current / recent.iloc[-60] - 1) * 100 if n >= 60 else np.nan

        # --- Volatility ---
        vol_20d = recent.pct_change().tail(20).std() * np.sqrt(252) * 100
        vol_60d = recent.pct_change().tail(60).std() * np.sqrt(252) * 100 if n >= 60 else np.nan

        # --- 52-week range ---
        high_52w = recent.tail(252).max() if n >= 252 else recent.max()
        low_52w = recent.tail(252).min() if n >= 252 else recent.min()
        drawdown_60d = (current / recent.tail(60).max() - 1) * 100 if n >= 60 else np.nan

        # --- Volume proxy (price * return trend) ---
        vpt = (recent.pct_change().fillna(0) * (1 + recent.pct_change().fillna(0))).tail(20).sum() * 100

        def _r(v):
            if isinstance(v, str):
                return v
            return round(v, 2) if not (isinstance(v, float) and np.isnan(v)) else "N/A"

        return {
            "current_price": round(current, 2),
            "sma20": _r(sma20),
            "sma50": _r(sma50),
            "ema12": _r(ema12),
            "ema26": _r(ema26),
            "rsi14": _r(rsi),
            "macd_line": _r(macd_series.iloc[-1]),
            "macd_signal": _r(macd_signal_val),
            "macd_histogram": _r(macd_hist),
            "stoch_k_14": _r(stoch_k),
            "bb_position": _r(bb_position),
            "bb_upper": _r(bb_upper),
            "bb_lower": _r(bb_lower),
            "atr_14": _r(atr),
            "vol_20d_ann_pct": _r(vol_20d),
            "vol_60d_ann_pct": _r(vol_60d),
            "return_5d_pct": _r(ret_5d),
            "return_20d_pct": _r(ret_20d),
            "return_60d_pct": _r(ret_60d),
            "drawdown_60d_pct": _r(drawdown_60d),
            "volume_price_trend": _r(vpt),
            "pct_from_52w_high": _r((current / high_52w - 1) * 100),
            "pct_from_52w_low": _r((current / low_52w - 1) * 100),
        }
