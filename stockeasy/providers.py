from datetime import date, datetime, timedelta, timezone
import io
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from stockeasy.models import Instrument


def normalize_history(raw: pd.DataFrame) -> pd.DataFrame:
    if raw is None or raw.empty:
        raise ValueError("数据源没有返回该区间的数据")
    frame = raw.copy()
    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = frame.columns.get_level_values(0)
    if isinstance(frame.index, pd.DatetimeIndex):
        frame = frame.reset_index()
        frame = frame.rename(columns={frame.columns[0]: "date"})
    mapping = {"日期": "date", "净值日期": "date", "开盘": "open", "最高": "high", "最低": "low",
               "收盘": "close", "单位净值": "close", "成交量": "volume", "Date": "date", "Datetime": "date",
               "Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"}
    frame = frame.rename(columns=mapping)
    if "date" not in frame or "close" not in frame:
        raise ValueError("数据源缺少日期或价格字段")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    if frame["date"].dt.tz is not None:
        frame["date"] = frame["date"].dt.tz_localize(None)
    frame["date"] = frame["date"].dt.normalize()
    for column in ["close", "open", "high", "low", "volume"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce") if column in frame else np.nan
    frame = frame.loc[frame["date"].notna() & np.isfinite(frame["close"]) & (frame["close"] > 0)]
    frame = frame.drop_duplicates("date", keep="last").sort_values("date").reset_index(drop=True)
    if frame.empty:
        raise ValueError("数据源未返回有效的正价格")
    return frame[["date", "open", "high", "low", "close", "volume"]]


def source_name(instrument):
    if instrument.market in {"US", "HK"}:
        return "Yahoo Finance · yfinance"
    return "天天基金 · AKShare" if instrument.market == "FUND" else "东方财富"


class Providers:
    """Run upstream libraries in a child process to enforce a hard UI deadline."""
    def _run(self, operation, instrument, **kwargs):
        request = {"operation": operation, "instrument": instrument.__dict__, **kwargs}
        try:
            process = subprocess.run([sys.executable, "-m", "stockeasy.worker"],
                                     input=json.dumps(request), text=True, capture_output=True, timeout=25,
                                     cwd=Path(__file__).resolve().parents[1])
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("数据源响应超过 25 秒，请稍后重试或使用本地缓存") from exc
        marker = "STOCKEASY_RESULT="
        output = next((line[len(marker):] for line in reversed(process.stdout.splitlines()) if line.startswith(marker)), None)
        if output is None:
            raise RuntimeError("数据源连接失败，请检查网络或稍后重试")
        result = json.loads(output)
        if "error" in result:
            raise RuntimeError(result["error"])
        return result

    def history(self, instrument, start, end, adjust):
        result = self._run("history", instrument, start=start.isoformat(), end=end.isoformat(), adjust=adjust)
        return pd.read_json(io.StringIO(result["frame"]), orient="table")

    def quote(self, instrument):
        return self._run("quote", instrument)


def fetch_history(instrument, start, end, adjust):
    if instrument.market in {"HK", "US"}:
        import yfinance as yf
        if adjust not in {"raw", "qfq"}:
            raise ValueError("海外行情仅支持原始价格或 Yahoo 复权")
        symbol = f"{int(instrument.symbol):04d}.HK" if instrument.market == "HK" else instrument.symbol
        raw = yf.Ticker(symbol).history(start=start.isoformat(), end=(end + timedelta(days=1)).isoformat(),
                                        auto_adjust=adjust == "qfq", actions=False, timeout=10, raise_errors=True)
    else:
        import akshare as ak
        adjustment = {"raw": "", "qfq": "qfq", "hfq": "hfq"}[adjust]
        if instrument.market == "FUND":
            raw = ak.fund_open_fund_info_em(symbol=instrument.symbol, indicator="单位净值走势")
        else:
            function = ak.fund_etf_hist_em if instrument.market == "ETF" else ak.stock_zh_a_hist
            raw = function(symbol=instrument.symbol, period="daily", start_date=start.strftime("%Y%m%d"),
                           end_date=end.strftime("%Y%m%d"), adjust=adjustment)
    frame = normalize_history(raw)
    return frame.loc[frame.date.between(pd.Timestamp(start), pd.Timestamp(end))].reset_index(drop=True)


def fetch_quote(instrument):
    if instrument.market in {"US", "HK"}:
        import yfinance as yf
        symbol = f"{int(instrument.symbol):04d}.HK" if instrument.market == "HK" else instrument.symbol
        ticker = yf.Ticker(symbol)
        frame = ticker.history(period="5d", interval="1m", auto_adjust=False, timeout=8, raise_errors=True)
        if frame.empty:
            raise ValueError("没有可用的分钟行情")
        close = frame["Close"].dropna()
        daily = ticker.history(period="5d", auto_adjust=False, timeout=8, raise_errors=True)["Close"].dropna()
        last_day = close.index[-1].date()
        previous = daily.loc[[t.date() < last_day for t in daily.index]]
        return {"price": float(close.iloc[-1]), "previous_close": float(previous.iloc[-1]) if len(previous) else None,
                "market_time": close.index[-1].isoformat(), "kind": "minute"}
    import akshare as ak
    if instrument.market == "FUND":
        frame = normalize_history(ak.fund_open_fund_info_em(symbol=instrument.symbol, indicator="单位净值走势"))
        return {"price": float(frame.close.iloc[-1]), "previous_close": float(frame.close.iloc[-2]) if len(frame) > 1 else None,
                "market_time": frame.date.iloc[-1].strftime("%Y-%m-%d"), "kind": "nav"}
    if instrument.market == "ETF":
        # AKShare's single-stock helper chooses the wrong exchange for Shanghai ETFs;
        # request the same upstream's single-security endpoint with an explicit ID.
        # Avoid downloading all ETFs on every watchlist refresh.
        import requests
        market = "1" if instrument.symbol.startswith(("5", "6")) else "0"
        response = requests.get("https://push2.eastmoney.com/api/qt/stock/get",
                                params={"secid": f"{market}.{instrument.symbol}", "fields": "f43,f60,f86", "fltt": "2"}, timeout=8)
        response.raise_for_status()
        data = response.json().get("data")
        if not data:
            raise ValueError("未找到该 ETF 的报价")
        updated = data.get("f86")
        return {"price": float(data["f43"]), "previous_close": float(data["f60"]),
                "market_time": datetime.fromtimestamp(updated, timezone.utc).isoformat() if updated else None, "kind": "quote"}
    data = ak.stock_bid_ask_em(symbol=instrument.symbol)
    values = dict(zip(data["item"], data["value"]))
    return {"price": float(values["最新"]), "previous_close": float(values["昨收"]),
            "market_time": None, "kind": "quote"}
