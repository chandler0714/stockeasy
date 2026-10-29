from datetime import date, timedelta
import time
import unittest

import numpy as np
import pandas as pd

from stockeasy.discovery import HistoryScanner, assess, available_candidates, build_report
from stockeasy.models import DataResult, DEFAULT_WATCHLIST, Instrument
from stockeasy.feeds import QuoteFeed

TODAY = date(2026, 10, 29)
ITEM = Instrument.create("ETF", "510300", "沪深300 ETF")


def history(prices, volumes=None, stale=False, end=TODAY):
    return DataResult(pd.DataFrame({"date": pd.bdate_range(end=end, periods=len(prices)),
                                   "close": prices, "volume": volumes if volumes is not None else np.nan}),
                      "test source", "2026-10-29T00:00:00+00:00", stale=stale)


class DiscoveryTests(unittest.TestCase):
    def test_trend_reason_uses_measured_momentum(self):
        idea = assess(ITEM, history(np.linspace(100, 130, 60)), TODAY)
        self.assertIn("趋势延续", idea.categories)
        self.assertIn("20 日", " ".join(idea.reasons))
        self.assertGreater(idea.momentum20, 0)
        self.assertEqual(idea.as_of, TODAY.isoformat())

    def test_volume_signal_uses_prior_twenty_observations(self):
        idea = assess(ITEM, history(np.full(60, 100.), [100] * 59 + [200]), TODAY)
        self.assertIn("量能变化", idea.categories)
        self.assertEqual(idea.volume_ratio, 2)
        self.assertNotIn("量能变化", assess(ITEM, history(np.full(60, 100.)), TODAY).categories)

    def test_recovery_reason_is_distinct_from_trend(self):
        prices = np.concatenate([np.linspace(130, 80, 55), np.linspace(81, 90, 5)])
        idea = assess(ITEM, history(prices), TODAY)
        self.assertIn("回撤修复", idea.categories)
        self.assertLess(idea.drawdown, -.05)

    def test_invalid_stale_old_or_short_history_is_not_recommended(self):
        for result in [history([100] * 10), history([100] * 60, stale=True),
                       history([100] * 60, end=TODAY - timedelta(days=20)),
                       history([100] * 60, end=TODAY + timedelta(days=1)), history([float("nan")] * 60)]:
            self.assertIsNone(assess(ITEM, result, TODAY))

    def test_watchlist_and_discovery_candidates_are_disjoint(self):
        selected = DEFAULT_WATCHLIST
        candidates = available_candidates(selected)
        self.assertTrue(candidates)
        self.assertFalse({item.key for item in candidates} & {item.key for item in selected})
        self.assertEqual(len(candidates), len({item.key for item in candidates}))

    def test_report_includes_risk_without_forcing_recommendation(self):
        crash = history(np.linspace(100, 60, 60))
        report = build_report({ITEM.key: (ITEM, crash)}, TODAY)
        self.assertTrue(any("回撤" in alert.reason for alert in report.risks))
        self.assertEqual(report.eligible, 1)
        self.assertEqual(len(report.ideas), 0)

    def test_background_scan_is_nonblocking_and_does_not_restart_pending_tasks(self):
        class SlowService:
            calls = 0

            def history(self, instrument, start, end, adjust, force=False):
                self.calls += 1
                time.sleep(.15)
                return history(np.linspace(100, 130, 60))

        service = SlowService()
        scanner = HistoryScanner(service, workers=1)
        try:
            before = time.monotonic()
            scanner.start([ITEM], TODAY)
            self.assertLess(time.monotonic() - before, .1)
            scanner.start([ITEM], TODAY)
            time.sleep(.2)
            results, errors, pending = scanner.snapshot()
            self.assertEqual(pending, 0)
            self.assertEqual(len(results), 1)
            self.assertEqual(errors, {})
            self.assertEqual(service.calls, 1)
        finally:
            scanner.close()

    def test_quote_feed_does_not_block_and_keeps_requested_interval(self):
        class SlowQuotes:
            max_age = None

            def quote(self, instrument, force=False, max_age_seconds=60):
                self.max_age = max_age_seconds
                time.sleep(.1)
                return "quote result"

        source = SlowQuotes()
        feed = QuoteFeed(source, workers=1)
        try:
            feed.refresh([ITEM], interval=5)
            self.assertIn(ITEM.key, feed.snapshot()[2])
            time.sleep(.15)
            self.assertEqual(feed.snapshot()[0][ITEM.key], "quote result")
            self.assertEqual(source.max_age, 5)
        finally:
            feed.close()

    def test_paused_quote_feed_collects_results_without_scheduling_more(self):
        class Quotes:
            calls = 0

            def quote(self, instrument, force=False, max_age_seconds=60):
                self.calls += 1
                return "completed"

        source = Quotes()
        feed = QuoteFeed(source, workers=1)
        try:
            feed.refresh([ITEM], interval=.01, paused=True)
            time.sleep(.03)
            feed.refresh([ITEM], interval=.01, paused=True)
            self.assertEqual(feed.snapshot()[0][ITEM.key], "completed")
            self.assertEqual(source.calls, 1)
            feed.refresh([ITEM], interval=.01, force=True, paused=True)
            time.sleep(.03)
            self.assertEqual(source.calls, 2)
        finally:
            feed.close()


if __name__ == "__main__":
    unittest.main()
