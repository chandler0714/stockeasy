import os
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
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any("演示" in item.value for item in app.warning))
        self.assertGreaterEqual(len(app.metric), 4)
        self.assertGreaterEqual(len(app.dataframe), 1)
        self.assertTrue(any("导出" in str(item.label) for item in app.get("download_button")))
        # Demo never creates or fills the real market cache.
        self.assertFalse((Path(self.temp.name) / "market.sqlite").exists())

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
