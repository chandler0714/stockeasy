import os
from datetime import date
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")

class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.environment = patch.dict(os.environ, {"STOCKEASY_DATA_DIR": self.temp.name, "STOCKEASY_DEMO": "1"})
        self.environment.start()

    def tearDown(self):
        self.environment.stop()
        self.temp.cleanup()

    def test_demo_dashboard_renders_analysis_without_network(self):
        app = AppTest.from_file(APP, default_timeout=20).run()
        app.radio(key="workspace").set_value("深度分析").run()
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any("演示" in item.value for item in app.warning))
        self.assertGreaterEqual(len(app.metric), 4)
        self.assertGreaterEqual(len(app.dataframe), 1)
        self.assertTrue(any("导出" in str(item.label) for item in app.get("download_button")))
        # Demo never creates or fills the real market cache.
        self.assertFalse((Path(self.temp.name) / "market.sqlite").exists())

    def test_pc_dashboard_has_daily_ideas_and_candidate_actions(self):
        app = AppTest.from_file(APP, default_timeout=20).run()
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any("当日推荐" in item.value for item in app.markdown))
        self.assertTrue(any("我的自选" in item.value for item in app.markdown))
        self.assertTrue(any("风险观察" in item.value for item in app.markdown))
        app.button(key="discover_add_ETF:159915").click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertIn("ETF:159915", app.selectbox(key="selected_key").options)
        self.assertFalse(any(button.key == "discover_add_ETF:159915" for button in app.button))

    def test_watchlist_view_and_remove_controls_work(self):
        app = AppTest.from_file(APP, default_timeout=20).run()
        app.button(key="watch_inspect_CN:600519").click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.radio(key="workspace").value, "深度分析")
        self.assertEqual(app.selectbox(key="selected_key").value, "CN:600519")
        app.button(key="watch_remove_ETF:510300").click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertNotIn("ETF:510300", app.selectbox(key="selected_key").options)

    def test_three_research_engines_run_in_demo(self):
        app = AppTest.from_file(APP, default_timeout=40).run()
        app.radio(key="workspace").set_value("量化研究").run()
        self.assertEqual(len(app.exception), 0)
        app.button(key="run_risk").click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any("QuantStats" in item.value for item in app.caption))
        app.button(key="run_backtest").click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any("Backtesting.py" in item.value for item in app.caption))
        app.button(key="run_portfolio").click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any("PyPortfolioOpt" in item.value for item in app.caption))
        self.assertFalse(app.error)
        self.assertTrue(any("配置权重" in item.label for item in app.get("download_button")))

    def test_research_parameters_invalidate_old_result(self):
        app = AppTest.from_file(APP, default_timeout=40).run()
        app.radio(key="workspace").set_value("量化研究").run()
        app.button(key="run_risk").click().run()
        app.selectbox(key="risk_asset").set_value("ETF:518880").run()
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any("参数已改变" in item.value for item in app.info))

    def test_beijing_midnight_rolls_header_and_daily_scan_forward(self):
        calls = 0

        def advancing_day():
            nonlocal calls
            calls += 1
            return date(2026, 10, 29) if calls == 1 else date(2026, 10, 30)

        with patch("stockeasy.presentation.beijing_day", side_effect=advancing_day):
            app = AppTest.from_file(APP, default_timeout=20).run()
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any("2026.10.30" in item.value for item in app.markdown))

    def test_add_and_remove_watchlist(self):
        app = AppTest.from_file(APP, default_timeout=20).run()
        app.selectbox(key="new_market").set_value("US")
        app.text_input(key="new_symbol").set_value("MSFT")
        app.text_input(key="new_name").set_value("Microsoft")
        app.button(key="add_watch").click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertIn("US:MSFT", app.selectbox(key="selected_key").options)
        app.selectbox(key="remove_key").set_value("US:MSFT")
        app.button(key="remove_watch").click().run()
        self.assertNotIn("US:MSFT", app.selectbox(key="selected_key").options)

    def test_invalid_symbol_is_actionable(self):
        app = AppTest.from_file(APP, default_timeout=20).run()
        app.text_input(key="new_symbol").set_value("invalid")
        app.button(key="add_watch").click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any("6 位数字" in item.value for item in app.error))

    def test_auto_refresh_enabled_by_default_and_can_pause(self):
        app = AppTest.from_file(APP, default_timeout=20).run()
        self.assertEqual(app.selectbox(key="refresh_interval_v3").value, "每 5 秒")
        self.assertTrue(any("自动刷新中" in item.value and "5 秒" in item.value for item in app.caption))
        app.selectbox(key="refresh_interval_v3").set_value("每 15 秒").run()
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any("自动刷新中" in item.value and "15 秒" in item.value for item in app.caption))
        app.selectbox(key="refresh_interval_v3").set_value("暂停（手动刷新）").run()
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any("自动刷新已暂停" in item.value for item in app.caption))

    def test_empty_watchlist_can_be_recovered(self):
        app = AppTest.from_file(APP, default_timeout=20).run()
        while app.selectbox(key="remove_key").options:
            app.button(key="remove_watch").click().run()
            if not any(item.key == "remove_key" for item in app.selectbox):
                break
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any("添加" in item.value for item in app.info))


if __name__ == "__main__":
    unittest.main()
