from dataclasses import replace
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from stockeasy.models import Instrument
from stockeasy.research import performance_html, performance_report, price_panel, validate_currency
from stockeasy.backtests import run_backtest
from stockeasy.portfolio import optimize_portfolio


def history(close, start="2025-01-02"):
    close = np.asarray(close, dtype=float)
    return pd.DataFrame({"date": pd.bdate_range(start=start, periods=len(close)), "open": close * .999,
                         "high": close * 1.01, "low": close * .99, "close": close,
                         "volume": np.full(len(close), 10000.)})


class ResearchTests(unittest.TestCase):
    def test_price_alignment_uses_intersection_without_forward_fill(self):
        a = history([100, 101, 102, 103, 104])
        b = history([10, 11, 12, 13, 14]).drop(index=2)
        panel = price_panel({"A": a, "B": b}, minimum=3)
        self.assertEqual(len(panel), 4)
        self.assertNotIn(a.date.iloc[2], panel.index)
        self.assertFalse(panel.isna().any().any())

    def test_invalid_or_insufficient_prices_are_rejected(self):
        bad = history([100] * 40)
        bad["close"] = np.nan
        with self.assertRaises(ValueError):
            price_panel({"A": bad}, minimum=30)
        with self.assertRaises(ValueError):
            price_panel({"A": history([1, 2, 3])}, minimum=30)

    def test_cross_currency_analysis_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_currency([Instrument.create("CN", "600519"), Instrument.create("US", "AAPL")])

    def test_quantstats_return_and_drawdown_use_actual_series(self):
        close = np.r_[np.full(30, 100.), 120., 90., 99.]
        result = performance_report({"A": history(close), "B": history(np.full(len(close), 100.))}, "A", "B")
        self.assertAlmostEqual(result.metrics["total_return"], -.01)
        self.assertAlmostEqual(result.metrics["max_drawdown"], -.25)
        self.assertAlmostEqual(result.metrics["benchmark_return"], 0)
        self.assertAlmostEqual(result.metrics["excess_return"], -.01)
        self.assertEqual(len(result.returns), len(close) - 1)

    def test_report_rejects_large_jump_that_quantstats_can_misread(self):
        jump = history(np.r_[10., np.full(29, 30.)])
        steady = history(np.linspace(100, 105, 30))
        for frames, benchmark in [({"A": jump}, None), ({"A": steady, "B": jump}, "B")]:
            with self.assertRaisesRegex(ValueError, "100%"):
                performance_report(frames, "A", benchmark)
        valid = performance_report({"A": steady}, "A")
        ambiguous = replace(valid, returns=pd.Series(np.r_[2., np.zeros(28)], index=valid.returns.index))
        with patch("stockeasy.research.qs.reports.html") as report:
            with self.assertRaisesRegex(ValueError, "100%"):
                performance_html(ambiguous)
            report.assert_not_called()

    def test_backtest_executes_next_open_in_lots_with_costs(self):
        close = 100 + np.arange(240) * .03 + 12 * np.sin(np.arange(240) / 10)
        frame = history(close)
        result = run_backtest(frame, strategy="均线交叉", fast=5, slow=15, cash=100000,
                              commission=.001, spread=0, lot_size=100, allocation=.8)
        self.assertGreater(len(result.trades), 2)
        self.assertTrue((result.trades.Size % 100 == 0).all())
        self.assertTrue((result.trades.ExitBar > result.trades.EntryBar).all())
        self.assertGreater(result.trades.Commission.sum(), 0)
        fast = frame.close.rolling(5).mean()
        slow = frame.close.rolling(15).mean()
        for bar in result.trades.EntryBar:
            self.assertGreater(fast.iloc[bar - 1], slow.iloc[bar - 1])
            self.assertLessEqual(fast.iloc[bar - 2], slow.iloc[bar - 2])

    def test_backtest_rejects_missing_ohlc_and_invalid_windows(self):
        frame = history(np.linspace(100, 130, 100))
        frame["open"] = np.nan
        with self.assertRaises(ValueError):
            run_backtest(frame)
        with self.assertRaises(ValueError):
            run_backtest(history(np.linspace(100, 130, 100)), fast=30, slow=10)

    def test_optimizer_uses_training_only_and_respects_weight_cap(self):
        rng = np.random.default_rng(42)
        prices = pd.DataFrame(100 * np.cumprod(1 + rng.normal([.0005, .0002, .0003], [.015, .005, .008], (180, 3)), axis=0),
                              index=pd.bdate_range("2025-01-02", periods=180), columns=["A", "B", "C"])
        result = optimize_portfolio(prices, max_weight=.6)
        self.assertAlmostEqual(result.weights.sum(), 1, places=6)
        self.assertTrue((result.weights >= -1e-7).all())
        self.assertLessEqual(result.weights.max(), .600001)
        self.assertLess(result.train_end, result.test_start)
        changed = prices.copy()
        changed.iloc[145:, 0] *= 10
        other = optimize_portfolio(changed, max_weight=.6)
        np.testing.assert_allclose(result.weights, other.weights, atol=1e-7)
        self.assertNotEqual(result.curves.iloc[-1, 0], other.curves.iloc[-1, 0])

    def test_optimizer_rejects_infeasible_cap_and_short_data(self):
        prices = pd.DataFrame({"A": np.arange(100, 250), "B": np.arange(200, 350)}, index=pd.bdate_range("2025-01-02", periods=150))
        with self.assertRaises(ValueError):
            optimize_portfolio(prices, max_weight=.4)
        with self.assertRaises(ValueError):
            optimize_portfolio(prices.iloc[:20])


if __name__ == "__main__":
    unittest.main()
