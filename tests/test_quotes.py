import unittest
from unittest.mock import patch
from types import SimpleNamespace

from stockeasy.models import Instrument
from stockeasy import providers


def wire(symbol, code, price, previous, stamp):
    # Tencent's fixed-position wire format, independently checked against
    # actual CN/ETF/HK/US responses; unused positions stay empty.
    fields = [""] * 40
    fields[0:5] = ["200", "name", code, price, previous]
    fields[30] = stamp
    return f'v_{symbol}="' + "~".join(fields) + '";'


class QuoteSourceTests(unittest.TestCase):
    def test_live_quote_uses_reachable_snapshot_before_yahoo(self):
        raw = wire("usSPY", "SPY.AM", "772.31", "769.66", "2026-10-28 16:00:01")
        response = SimpleNamespace(text=raw, raise_for_status=lambda: None)
        with patch("requests.Session.get", return_value=response), patch("yfinance.Ticker", side_effect=RuntimeError("Yahoo is rate limited")):
            quote = providers.fetch_quote(Instrument.create("US", "SPY"))
        self.assertEqual(quote["price"], 772.31)
        self.assertEqual(quote["market_time"], "2026-10-28T16:00:01-04:00")
        self.assertIn("腾讯", quote["source"])

    def test_original_source_fallback_is_labeled_and_errors_are_safe(self):
        import requests
        item = Instrument.create("US", "SPY")
        with patch.object(providers, "fetch_tencent_quote", side_effect=requests.ConnectionError("secret-proxy-password")), patch.object(providers, "fetch_original_quote", return_value={"price": 770., "previous_close": 769.}):
            result = providers.fetch_quote(item)
            self.assertEqual(result["price"], 770.)
            self.assertEqual(result["source"], "Yahoo Finance · yfinance")
        failure = requests.HTTPError("secret-proxy-password", response=SimpleNamespace(status_code=429))
        with patch.object(providers, "fetch_tencent_quote", side_effect=requests.ConnectionError("secret-proxy-password")), patch.object(providers, "fetch_original_quote", side_effect=failure):
            with self.assertRaises(providers.QuoteUnavailable) as raised:
                providers.fetch_quote(item)
        self.assertIn("429", str(raised.exception))
        self.assertNotIn("secret-proxy-password", str(raised.exception))

    def test_pending_retry_does_not_hide_failure_or_stale_cache(self):
        from stockeasy import presentation
        status = getattr(presentation, "quote_status", None)
        self.assertIsNotNone(status)
        self.assertIn("失败", status(None, "source offline", pending=True))
        self.assertIn("重试", status(None, "source offline", pending=True))
        cached = SimpleNamespace(stale=True)
        self.assertIn("缓存", status(cached, "source offline", pending=True))

    def test_tencent_prices_identify_security_and_market_timezone(self):
        fixtures = [
            ("US", "SPY", "usSPY", "SPY.AM", "772.31", "769.66", "2026-10-28 16:00:01", "2026-10-28T16:00:01-04:00"),
            ("HK", "00700", "hk00700", "00700", "377.600", "387.600", "2026/10/29 15:47:06", "2026-10-29T15:47:06+08:00"),
            ("ETF", "510300", "sh510300", "510300", "4.111", "4.152", "20261029160210", "2026-10-29T16:02:10+08:00"),
            ("CN", "920001", "bj920001", "920001", "12", "10", "20261029150210", "2026-10-29T15:02:10+08:00"),
        ]
        parser = getattr(providers, "parse_tencent_quote", None)
        self.assertIsNotNone(parser, "Single-security Tencent responses need a validated parser")
        for market, symbol, remote, code, price, previous, stamp, expected in fixtures:
            with self.subTest(remote=remote):
                item = Instrument.create(market, symbol)
                result = parser(wire(remote, code, price, previous, stamp), item)
                self.assertEqual(result["price"], float(price))
                self.assertEqual(result["previous_close"], float(previous))
                self.assertEqual(result["market_time"], expected)
                self.assertIn("腾讯", result["source"])

    def test_tencent_invalid_or_wrong_security_never_becomes_a_quote(self):
        parser = getattr(providers, "parse_tencent_quote", None)
        self.assertIsNotNone(parser)
        item = Instrument.create("US", "SPY")
        for raw in ['v_pv_none_match="1";', wire("usAAPL", "AAPL.OQ", "343.83", "347.10", "2026-10-28 16:00:01"),
                    wire("usSPY", "AAPL.OQ", "772.31", "769.66", "2026-10-28 16:00:01"),
                    wire("usSPY", "SPY.AM", "nan", "769.66", "2026-10-28 16:00:01"),
                    wire("usSPY", "SPY.AM", "0", "769.66", "2026-10-28 16:00:01"),
                    wire("usSPY", "SPY.AM", "772.31", "769.66", "bad")]:
            with self.subTest(raw=raw[:40]), self.assertRaises(ValueError):
                parser(raw, item)

    def test_service_preserves_actual_quote_source_and_cache(self):
        import tempfile
        from pathlib import Path
        from stockeasy.service import MarketService
        from stockeasy.storage import Store
        item = Instrument.create("US", "SPY")
        provider = SimpleNamespace(quote=lambda item: {"price": 772.31, "previous_close": 769.66,
                                                      "source": "腾讯财经 · 报价快照", "market_time": "2026-10-28T16:00:01-04:00"})
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder) / "test.sqlite")
            service = MarketService(store, provider)
            quote = service.quote(item)
            self.assertEqual(quote.source, "腾讯财经 · 报价快照")
            self.assertEqual(store.load_quote(item.key).source, quote.source)
            self.assertFalse(quote.stale)


if __name__ == "__main__":
    unittest.main()
