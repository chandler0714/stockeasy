"""Synthetic, repeatable previews; never written to the real market cache."""
import hashlib
from datetime import date, timedelta

import numpy as np
import pandas as pd

from stockeasy.models import DataResult, QuoteResult
from stockeasy.service import utc_now

BASE = {"600519": 1480, "510300": 4.12, "00700": 418, "AAPL": 225, "SPY": 585, "110022": 3.65}


def demo_history(instrument, start, end):
    seed = int(hashlib.sha256(instrument.key.encode()).hexdigest()[:8], 16)
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2000-01-01", max(end, date(2027, 1, 1)))
    returns = rng.normal(.00025, .012 if instrument.market != "FUND" else .007, len(dates))
    close = np.exp(np.cumsum(returns))
    anchor = np.searchsorted(dates, pd.Timestamp("2026-10-29"), side="right") - 1
    close = close / close[anchor] * BASE.get(instrument.symbol, 100)
    opening = close * (1 + rng.normal(0, .004, len(dates)))
    frame = pd.DataFrame({"date": dates, "open": opening, "close": close,
                          "high": np.maximum(close, opening) * (1 + rng.uniform(.001, .015, len(dates))),
                          "low": np.minimum(close, opening) * (1 - rng.uniform(.001, .015, len(dates))),
                          "volume": rng.integers(100000, 9000000, len(dates)).astype(float)})
    if instrument.market == "FUND":
        frame[["open", "high", "low", "volume"]] = np.nan
    frame = frame.loc[frame.date.between(pd.Timestamp(start), pd.Timestamp(end))].reset_index(drop=True)
    return DataResult(frame, "合成演示数据", utc_now())


def demo_quote(instrument, today):
    frame = demo_history(instrument, today - timedelta(days=10), today).frame
    return QuoteResult(float(frame.close.iloc[-1]), float(frame.close.iloc[-2]), "合成演示数据", utc_now(),
                       frame.date.iloc[-1].strftime("%Y-%m-%d"), kind="demo")
