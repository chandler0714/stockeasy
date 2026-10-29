"""Bounded daily-bar strategy research using Backtesting.py."""
from dataclasses import dataclass
import warnings

import numpy as np
import pandas as pd
from backtesting import Backtest, Strategy

from stockeasy.research import finite

STRATEGIES = ("均线交叉", "趋势延续", "回撤修复")


def moving_average(values, period):
    return pd.Series(values).rolling(period).mean().to_numpy()


class ResearchStrategy(Strategy):
    kind = "均线交叉"
    fast = 10
    slow = 30
    lot_size = 100
    allocation = .9

    def init(self):
        close = self.data.Close
        if self.kind == "均线交叉":
            self.fast_ma = self.I(moving_average, close, self.fast)
            self.slow_ma = self.I(moving_average, close, self.slow)
        elif self.kind == "趋势延续":
            self.ma20 = self.I(moving_average, close, 20)
            self.past_ma20 = self.I(lambda values: pd.Series(values).rolling(20).mean().shift(5).to_numpy(), close)
            self.ret20 = self.I(lambda values: pd.Series(values).pct_change(20, fill_method=None).to_numpy(), close)
        else:
            self.peak = self.I(lambda values: pd.Series(values).rolling(60).max().to_numpy(), close)
            self.ret5 = self.I(lambda values: pd.Series(values).pct_change(5, fill_method=None).to_numpy(), close)

    def next(self):
        price = float(self.data.Close[-1])
        if self.kind == "均线交叉":
            enter = self.fast_ma[-1] > self.slow_ma[-1] and self.fast_ma[-2] <= self.slow_ma[-2]
            leave = self.fast_ma[-1] < self.slow_ma[-1] and self.fast_ma[-2] >= self.slow_ma[-2]
        elif self.kind == "趋势延续":
            enter = price > self.ma20[-1] and self.ma20[-1] > self.past_ma20[-1] and self.ret20[-1] > .02
            leave = price < self.ma20[-1]
        else:
            drawdown = price / self.peak[-1] - 1
            enter = drawdown <= -.05 and self.ret5[-1] >= .015
            leave = self.ret5[-1] <= -.02 or drawdown >= -.01
        if self.position:
            if leave:
                self.position.close()
        elif enter:
            # Current close sizing only. Next-open gaps can cause engine rejection;
            # never inspect that future open to determine today's order quantity.
            lots = int(self.equity * self.allocation / price / self.lot_size)
            if lots > 0:
                self.buy(size=lots * self.lot_size)


@dataclass
class BacktestResult:
    metrics: dict
    equity: pd.DataFrame
    trades: pd.DataFrame
    open_trades: int
    dropped_rows: int


def run_backtest(frame, strategy="均线交叉", fast=10, slow=30, cash=100000, commission=.0005,
                 spread=.0005, lot_size=100, allocation=.9):
    if strategy not in STRATEGIES:
        raise ValueError("不支持的策略")
    if not 2 <= fast < slow <= 250:
        raise ValueError("均线参数需满足 2 ≤ 短周期 < 长周期 ≤ 250")
    if not np.isfinite([cash, commission, spread, allocation]).all() or cash <= 0 or not 0 <= commission <= .05 or not 0 <= spread <= .05 or not 0 < allocation <= .95:
        raise ValueError("资金、费用或使用比例无效；资金使用比例最高 95%")
    if not isinstance(lot_size, int) or lot_size < 1:
        raise ValueError("每手数量必须为正整数")
    required = ["date", "open", "high", "low", "close"]
    if not set(required) <= set(frame.columns):
        raise ValueError("缺少完整 OHLC 日线，不能生成价格或用基金净值代替开高低收")
    data = frame[required].copy()
    data["date"] = pd.to_datetime(data.date, errors="coerce")
    data[["open", "high", "low", "close"]] = data[["open", "high", "low", "close"]].apply(pd.to_numeric, errors="coerce")
    valid = data.date.notna() & np.isfinite(data[["open", "high", "low", "close"]]).all(axis=1) & (data[["open", "high", "low", "close"]] > 0).all(axis=1)
    valid &= data.high >= data[["open", "close", "low"]].max(axis=1)
    valid &= data.low <= data[["open", "close", "high"]].min(axis=1)
    data = data.loc[valid].drop_duplicates("date", keep="last").sort_values("date").set_index("date")
    warmup = slow if strategy == "均线交叉" else 25 if strategy == "趋势延续" else 60
    if len(data) < warmup + 10:
        raise ValueError(f"至少需要 {warmup + 10} 条完整 OHLC 日线；当前 {len(data)} 条")
    data.columns = ["Open", "High", "Low", "Close"]
    engine = Backtest(data, ResearchStrategy, cash=cash, commission=commission, spread=spread,
                      trade_on_close=False, exclusive_orders=True, finalize_trades=False)
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Some trades remain open.*")
        stats = engine.run(kind=strategy, fast=fast, slow=slow, lot_size=lot_size, allocation=allocation)
    metrics = {"total_return": finite(stats["Return [%]"] / 100), "max_drawdown": finite(stats["Max. Drawdown [%]"] / 100),
               "sharpe": finite(stats["Sharpe Ratio"]), "closed_trades": int(stats["# Trades"]),
               "win_rate": finite(stats["Win Rate [%]"] / 100), "final_equity": finite(stats["Equity Final [$]"])}
    curves = pd.DataFrame({"策略": stats["_equity_curve"]["Equity"] / cash * 100,
                           "买入持有对照（不计费用）": data.Close / data.Close.iloc[0] * 100})
    return BacktestResult(metrics, curves, stats["_trades"].copy(), len(stats["_strategy"].trades), len(frame) - len(data))
