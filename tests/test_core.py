import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from stockeasy.analytics import summarize
from stockeasy.models import Instrument
from stockeasy.providers import fetch_quote, normalize_history
from stockeasy.service import MarketService
from stockeasy.storage import Store


def bars():
    return pd.DataFrame({
        "date": pd.to_datetime(["2026-01-02", "2026-01-05", "2026-01-06"]),
        "open": [100., 110., 99.], "high": [101., 111., 100.],
        "low": [99., 109., 98.], "close": [100., 110., 99.],
        "volume": [10., 20., 30.],
    })


class FakeProvider:
    def __init__(self):
        self.failing = False
        self.history_calls = []

    def history(self, instrument, start, end, adjust):
        self.history_calls.append((start, end, adjust))
        if self.failing:
            raise RuntimeError("offline")
        return bars()

    def quote(self, instrument):
        if self.failing:
            raise RuntimeError("offline")
        return {"price": 99., "previous_close": 110., "market_time": "2026-01-06T15:00:00+08:00", "kind": "quote"}


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name) / "test.sqlite")
        self.instrument = Instrument.create("CN", "600519", "贵州茅台")
        self.provider = FakeProvider()
        self.service = MarketService(self.store, self.provider)

    def tearDown(self):
        self.temp.cleanup()

    def test_symbol_validation_and_canonicalization(self):
        self.assertEqual(Instrument.create("HK", "700").symbol, "00700")
        self.assertEqual(Instrument.create("US", "brk-b").symbol, "BRK-B")
        self.assertEqual(Instrument.create("CN", "000001").key, "CN:000001")
        for market, symbol in [("CN", "abc"), ("US", "../secret"), ("FUND", "123"), ("XX", "000001")]:
            with self.assertRaises(ValueError):
                Instrument.create(market, symbol)

    def test_normalize_chinese_columns_and_duplicates(self):
        raw = pd.DataFrame({"日期": ["2026-01-02", "2026-01-02", "bad"], "开盘": [1, 2, 3],
                            "最高": [2, 3, 4], "最低": [1, 1, 1], "收盘": ["1.5", "2.5", "4"], "成交量": [100, 200, 300]})
        normalized = normalize_history(raw)
        self.assertEqual(len(normalized), 1)
        self.assertEqual(normalized.iloc[0]["close"], 2.5)

    def test_normalize_yahoo_multiindex_and_timezone(self):
        raw = pd.DataFrame([[1, 2, .5, 1.5, 200]],
                           index=pd.DatetimeIndex(["2026-01-02"], tz="America/New_York"),
                           columns=pd.MultiIndex.from_tuples([(c, "AAPL") for c in ["Open", "High", "Low", "Close", "Volume"]]))
        normalized = normalize_history(raw)
        self.assertEqual(normalized.iloc[0]["date"], pd.Timestamp("2026-01-02"))
        self.assertEqual(normalized.iloc[0]["volume"], 200)

    def test_empty_or_invalid_history_rejected(self):
        for raw in [pd.DataFrame(), pd.DataFrame({"date": ["2026-01-02"], "close": [0]}), pd.DataFrame({"date": ["2026-01-02"], "close": [float("inf")]})]:
            with self.assertRaises(ValueError):
                normalize_history(raw)

    def test_return_and_drawdown(self):
        result = summarize(bars())
        self.assertAlmostEqual(result["return"], -.01)
        self.assertAlmostEqual(result["max_drawdown"], -.1)
        self.assertEqual(result["observations"], 3)
        self.assertIsNone(summarize(bars().iloc[:1])["return"])

    def test_watchlist_persists_and_preserves_leading_zero(self):
        instrument = Instrument.create("CN", "000001", "平安银行")
        self.store.save_watchlist([instrument])
        reloaded = Store(self.store.path).watchlist()
        self.assertEqual(reloaded[0].symbol, "000001")
        self.store.save_watchlist([])
        self.assertEqual(self.store.watchlist(), [])

    def test_history_fallback_reports_stale_and_original_fetch_time(self):
        first = self.service.history(self.instrument, date(2026, 1, 1), date(2026, 1, 7), "raw")
        self.provider.failing = True
        fallback = self.service.history(self.instrument, date(2026, 1, 1), date(2026, 1, 7), "raw", force=True)
        self.assertTrue(fallback.stale)
        self.assertEqual(fallback.fetched_at, first.fetched_at)
        self.assertIn("offline", fallback.error)
        self.assertEqual(len(fallback.frame), 3)

    def test_adjustment_cache_cannot_cross_contaminate(self):
        self.service.history(self.instrument, date(2026, 1, 1), date(2026, 1, 7), "raw")
        self.provider.failing = True
        with self.assertRaises(RuntimeError):
            self.service.history(self.instrument, date(2026, 1, 1), date(2026, 1, 7), "qfq")

    def test_history_extends_range_and_filters_results(self):
        self.service.history(self.instrument, date(2026, 1, 5), date(2026, 1, 7), "raw")
        result = self.service.history(self.instrument, date(2026, 1, 1), date(2026, 1, 7), "raw")
        self.assertEqual(self.provider.history_calls[-1][0], date(2026, 1, 1))
        self.assertEqual(len(result.frame), 3)

    def test_quote_failure_never_becomes_fresh(self):
        initial = self.service.quote(self.instrument)
        self.provider.failing = True
        fallback = self.service.quote(self.instrument, force=True)
        self.assertTrue(fallback.stale)
        self.assertEqual(fallback.fetched_at, initial.fetched_at)
        self.assertAlmostEqual(fallback.change_pct, -.1)

    def test_quote_cache_respects_selected_refresh_interval(self):
        initial = self.service.quote(self.instrument)
        initial.fetched_at = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()
        self.store.save_quote(self.instrument.key, initial)
        self.provider.quote = lambda item: {"price": 101., "previous_close": 100.}
        self.assertEqual(self.service.quote(self.instrument, max_age_seconds=15).price, 99.)
        self.assertEqual(self.service.quote(self.instrument, max_age_seconds=5).price, 101.)

    def test_daily_fund_nav_does_not_redownload_every_five_seconds(self):
        fund = Instrument.create("FUND", "110022")
        initial = self.service.quote(fund)
        initial.fetched_at = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()
        self.store.save_quote(fund.key, initial)
        self.provider.failing = True
        cached = self.service.quote(fund, max_age_seconds=5)
        self.assertFalse(cached.stale)
        self.assertEqual(cached.fetched_at, initial.fetched_at)
        # Manual refresh still tries the provider, reports the failure, and
        # preserves the old source timestamp instead of inventing a fresh NAV.
        self.assertTrue(self.service.quote(fund, force=True, max_age_seconds=5).stale)
        after_failure = self.service.quote(fund, max_age_seconds=5)
        self.assertTrue(after_failure.stale)
        self.assertIn("offline", after_failure.error)
        self.assertEqual(after_failure.fetched_at, initial.fetched_at)
        self.provider.failing = False
        recovered = self.service.quote(fund, force=True, max_age_seconds=5)
        self.assertFalse(recovered.stale)
        self.assertEqual(recovered.error, "")
        self.assertFalse(self.store.load_quote(fund.key).stale)

    def test_invalid_quote_not_cached(self):
        self.provider.quote = lambda instrument: {"price": float("nan"), "previous_close": 100}
        with self.assertRaises(ValueError):
            self.service.quote(self.instrument)

    def test_etf_quote_uses_etf_market_not_stock_code_heuristic(self):
        response = SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"data": {"f43": 4.2, "f60": 4.1, "f86": 1793257200}})
        with patch("stockeasy.providers.fetch_tencent_quote", side_effect=ValueError("unavailable")), patch("requests.get", return_value=response) as get:
            result = fetch_quote(Instrument.create("ETF", "510300"))
        self.assertEqual(get.call_args.kwargs["params"]["secid"], "1.510300")
        self.assertEqual(result["price"], 4.2)
        self.assertIsNotNone(result["market_time"])

    def test_adjusted_refresh_reloads_entire_covered_period(self):
        self.service.history(self.instrument, date(2026, 1, 1), date(2026, 1, 7), "qfq")
        self.service.history(self.instrument, date(2026, 1, 5), date(2026, 2, 1), "qfq", force=True)
        self.assertEqual(self.provider.history_calls[-1][0], date(2026, 1, 1))

    def test_partial_adjusted_refresh_preserves_cache(self):
        for adjustment in ["qfq", "hfq"]:
            with self.subTest(adjustment=adjustment):
                self.provider.history = lambda *args: bars()
                original = self.service.history(self.instrument, date(2026, 1, 1), date(2026, 1, 7), adjustment)
                self.provider.history = lambda *args: bars().iloc[-1:]
                result = self.service.history(self.instrument, date(2026, 1, 1), date(2026, 1, 7), adjustment, force=True)
                self.assertTrue(result.stale)
                self.assertEqual(len(result.frame), 3)
                self.assertEqual(result.fetched_at, original.fetched_at)
                self.assertEqual(len(self.store.load_history(self.instrument.key, adjustment).frame), 3)


if __name__ == "__main__":
    unittest.main()
