from types import SimpleNamespace
import unittest

from stockeasy.models import Instrument
from stockeasy.presentation import idea_html


def idea(prices, categories=("量能变化",)):
    return SimpleNamespace(
        instrument=Instrument.create("ETF", "159915", "创业板 ETF"),
        categories=categories, reasons=("成交量为前20日均量的1.62倍",),
        prices=prices, momentum20=-.254, as_of="2026-10-29",
        source="test source", risk="历史波动较大",
    )


class SignalPresentationTests(unittest.TestCase):
    def test_volume_interpretation_follows_latest_move_not_twenty_day_direction(self):
        # Same negative 20-observation trend; the newest move differs.
        falling = idea_html(idea([100., 90.]), "量能变化")
        rising = idea_html(idea([90., 100.]), "量能变化")
        self.assertIn("这条信息说明什么", falling)
        self.assertIn("最近一个交易日下跌 10.00%", falling)
        self.assertIn("最近一个交易日上涨 11.11%", rising)
        self.assertIn("交易更活跃", falling)

    def test_interpretation_matches_selected_category_on_multi_signal_card(self):
        sample = idea([100., 110.], ("趋势延续", "量能变化"))
        sample.reasons = ("趋势规则", "量能规则")
        trend = idea_html(sample, "趋势延续")
        volume = idea_html(sample, "量能变化")
        self.assertIn("上行均线", trend)
        self.assertIn("交易更活跃", volume)
        self.assertIn("量能规则", volume)


if __name__ == "__main__":
    unittest.main()
