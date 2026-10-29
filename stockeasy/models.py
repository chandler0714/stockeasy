from dataclasses import dataclass, field
from datetime import date, datetime
import re

import pandas as pd

MARKETS = {"CN": "A 股", "ETF": "境内 ETF", "HK": "港股", "US": "美股 / ETF", "FUND": "场外基金"}


@dataclass(frozen=True)
class Instrument:
    symbol: str
    name: str
    market: str
    currency: str

    @property
    def key(self) -> str:
        return f"{self.market}:{self.symbol}"

    @classmethod
    def create(cls, market: str, symbol: str, name: str = ""):
        symbol = symbol.strip().upper()
        if market not in MARKETS:
            raise ValueError("请选择支持的市场")
        if market in {"CN", "ETF", "FUND"} and not re.fullmatch(r"\d{6}", symbol):
            raise ValueError("境内股票和基金代码应为 6 位数字，例如 600519")
        if market == "HK":
            symbol = symbol.removesuffix(".HK")
            if not re.fullmatch(r"\d{1,5}", symbol):
                raise ValueError("港股代码应为 1～5 位数字，例如 00700")
            symbol = symbol.zfill(5)
        if market == "US" and not re.fullmatch(r"[A-Z][A-Z0-9.^-]{0,14}", symbol):
            raise ValueError("美股代码格式不正确，例如 AAPL、SPY、BRK-B")
        currency = "HKD" if market == "HK" else "USD" if market == "US" else "CNY"
        return cls(symbol, name.strip()[:40] or symbol, market, currency)


DEFAULT_WATCHLIST = [
    Instrument.create("CN", "600519", "贵州茅台"),
    Instrument.create("ETF", "510300", "沪深300 ETF"),
    Instrument.create("HK", "00700", "腾讯控股"),
    Instrument.create("US", "AAPL", "Apple"),
    Instrument.create("US", "SPY", "标普500 ETF"),
    Instrument.create("FUND", "110022", "易方达消费行业"),
]


@dataclass
class DataResult:
    frame: pd.DataFrame
    source: str
    fetched_at: str
    stale: bool = False
    error: str = ""
    range_start: str = ""
    range_end: str = ""


@dataclass
class QuoteResult:
    price: float
    previous_close: float | None
    source: str
    fetched_at: str
    market_time: str | None = None
    kind: str = "quote"
    stale: bool = False
    error: str = ""

    @property
    def change_pct(self):
        return self.price / self.previous_close - 1 if self.previous_close and self.previous_close > 0 else None
