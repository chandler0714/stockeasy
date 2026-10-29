"""Explainable observation-pool signals, not a whole-market investment ranking."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, timedelta
from threading import RLock
import time

import numpy as np
import pandas as pd

from stockeasy.models import DEFAULT_WATCHLIST, DataResult, Instrument

CATEGORIES = ("趋势延续", "量能变化", "回撤修复", "低波动")
CATALOG = DEFAULT_WATCHLIST + [
    Instrument.create("ETF", "159915", "创业板 ETF"),
    Instrument.create("ETF", "518880", "黄金 ETF"),
    Instrument.create("ETF", "513100", "纳指 ETF"),
    Instrument.create("CN", "600036", "招商银行"),
    Instrument.create("US", "QQQ", "纳斯达克100 ETF"),
    Instrument.create("US", "MSFT", "Microsoft"),
]
BENCHMARKS = [CATALOG[1], CATALOG[6], CATALOG[7], CATALOG[4]]


def available_candidates(selected):
    keys = {item.key for item in selected}
    return [item for item in CATALOG if item.key not in keys]


def universe(selected):
    return list({item.key: item for item in CATALOG + list(selected)}.values())


@dataclass
class Idea:
    instrument: Instrument
    categories: tuple[str, ...]
    reasons: tuple[str, ...]
    momentum5: float
    momentum20: float
    drawdown: float
    volatility: float
    volume_ratio: float | None
    as_of: str
    source: str
    prices: list[float]
    dates: list[str]
    risk: str


@dataclass
class Risk:
    instrument: Instrument
    reason: str
    as_of: str


@dataclass
class Report:
    ideas: list[Idea]
    risks: list[Risk]
    eligible: int
    total: int


def assess(instrument: Instrument, result: DataResult, today: date) -> Idea | None:
    if result.stale or result.frame.empty or not {"date", "close"} <= set(result.frame.columns):
        return None
    frame = result.frame.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    frame = frame.loc[frame.date.notna() & np.isfinite(frame.close) & (frame.close > 0)]
    frame = frame.drop_duplicates("date").sort_values("date")
    if len(frame) < 30:
        return None
    last_date = frame.date.iloc[-1].date()
    if not 0 <= (today - last_date).days <= 7:
        return None
    close = frame.close.iloc[-60:]
    momentum5 = float(close.iloc[-1] / close.iloc[-6] - 1)
    momentum20 = float(close.iloc[-1] / close.iloc[-21] - 1)
    ma20 = float(close.iloc[-20:].mean())
    prior_ma20 = float(close.iloc[-25:-5].mean())
    drawdown = float(close.iloc[-1] / close.max() - 1)
    volatility = float(close.pct_change().dropna().std(ddof=1) * np.sqrt(252))
    volume_ratio = None
    if "volume" in frame:
        volume = pd.to_numeric(frame.volume.iloc[-21:], errors="coerce")
        prior = volume.iloc[:-1]
        if len(prior) == 20 and prior.notna().all() and np.isfinite(volume).all() and (prior > 0).all() and volume.iloc[-1] >= 0:
            volume_ratio = float(volume.iloc[-1] / prior.mean())
    categories, reasons = [], []
    if close.iloc[-1] > ma20 and ma20 > prior_ma20 and momentum20 > .02:
        categories.append("趋势延续")
        reasons.append(f"20 日涨幅 {momentum20:+.1%}，价格站上向上的 20 日均线")
    if volume_ratio is not None and volume_ratio >= 1.5:
        categories.append("量能变化")
        reasons.append(f"最近交易日成交量为前 20 日均量的 {volume_ratio:.2f} 倍；放量不代表上涨")
    if drawdown <= -.05 and momentum5 >= .015:
        categories.append("回撤修复")
        reasons.append(f"距近 60 日高点仍回撤 {drawdown:.1%}，近 5 日回升 {momentum5:+.1%}")
    if volatility < .18 and abs(drawdown) < .08:
        categories.append("低波动")
        reasons.append(f"近 60 日年化波动 {volatility:.1%}、当前回撤 {drawdown:.1%}；不代表低风险")
    risk = "需观察趋势反转，历史信号不预测未来收益"
    if volatility >= .35:
        risk = f"年化波动 {volatility:.1%}，短期价格变化较大"
    elif drawdown <= -.15:
        risk = f"距近 60 日高点回撤 {drawdown:.1%}，修复尚不充分"
    elif instrument.market == "FUND":
        risk = "单位净值口径，未计分红再投；净值按日公布"
    return Idea(instrument, tuple(categories), tuple(reasons), momentum5, momentum20, drawdown, volatility,
                volume_ratio, last_date.isoformat(), result.source, close.astype(float).tolist(),
                frame.date.iloc[-len(close):].dt.strftime("%Y-%m-%d").tolist(), risk)


def build_report(results, today):
    ideas, risks, eligible = [], [], 0
    for instrument, result in results.values():
        idea = assess(instrument, result, today)
        if idea is None:
            continue
        eligible += 1
        if idea.drawdown <= -.15:
            risks.append(Risk(instrument, f"距近 60 日高点回撤 {idea.drawdown:.1%}", idea.as_of))
        if idea.volatility >= .35:
            risks.append(Risk(instrument, f"年化波动 {idea.volatility:.1%}，留意价格跳动", idea.as_of))
        if idea.categories:
            ideas.append(idea)
    # Diversify the first visible cards across reasons rather than force a pick.
    arranged, seen = [], set()
    ordered = sorted(ideas, key=lambda item: (-len(item.categories), -item.momentum20, item.instrument.key))
    for category in CATEGORIES:
        match = next((item for item in ordered if category in item.categories and item.instrument.key not in seen), None)
        if match:
            arranged.append(match)
            seen.add(match.instrument.key)
    arranged.extend(item for item in ordered if item.instrument.key not in seen)
    return Report(arranged, risks, eligible, len(results))


class HistoryScanner:
    """Single local bounded pool; UI polls snapshots without waiting for network."""
    def __init__(self, service, workers=4):
        self.service = service
        self.pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="stockeasy-scan")
        self.tasks = {}
        self.lock = RLock()

    def start(self, instruments, today, force=False):
        with self.lock:
            active = {item.key for item in instruments}
            # Dropped queued tasks must not outlive a changed observation pool.
            for key in set(self.tasks) - active:
                self.tasks[key][1].cancel()
                del self.tasks[key]
            for item in instruments:
                previous = self.tasks.get(item.key)
                if previous and (not previous[1].done() or (not force and previous[2] == today and time.monotonic() - previous[3] < 3600)):
                    continue
                adjustment = "raw" if item.market == "FUND" else "qfq"
                future = self.pool.submit(self.service.history, item, today - timedelta(days=160), today, adjustment, force=force)
                self.tasks[item.key] = (item, future, today, time.monotonic())

    def snapshot(self):
        results, errors, pending = {}, {}, 0
        with self.lock:
            for key, (item, future, _, _) in self.tasks.items():
                if not future.done():
                    pending += 1
                    continue
                try:
                    results[key] = (item, future.result())
                except Exception as exc:
                    errors[key] = str(exc)
        return results, errors, pending

    def close(self):
        self.pool.shutdown(wait=False, cancel_futures=True)
