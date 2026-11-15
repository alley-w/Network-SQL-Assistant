import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


class UITests(unittest.TestCase):
    def start(self):
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "ui.py")).run()
        self.assertFalse(app.exception)
        return app

    def test_load_without_model_call(self):
        with patch("network_sql.ui.generate_sql") as model:
            self.start()
            model.assert_not_called()

    def test_generate_review_execute_and_edit(self):
        with patch("network_sql.ui.generate_sql", return_value="SELECT COUNT(*) AS device_count FROM devices;") as model:
            app = self.start()
            app.text_area[0].input("How many devices?").run()
            app.button[0].click().run()
            self.assertEqual(model.call_count, 1)
            self.assertEqual(len(app.dataframe), 0)
            app.run()
            self.assertEqual(model.call_count, 1)
            app.button[1].click().run()
            self.assertEqual(app.dataframe[0].value.iloc[0, 0], 6)
            self.assertEqual(model.call_count, 1)
            app.text_area[0].input("How many sites?").run()
            self.assertEqual(len(app.dataframe), 0)
            self.assertEqual(len(app.button), 1)
            self.assertFalse(app.exception)

    def test_missing_date_skips_model(self):
        with patch("network_sql.ui.generate_sql") as model:
            app = self.start()
            app.text_area[0].input("CPU yesterday?").run()
            app.button[0].click().run()
            model.assert_not_called()
            self.assertIn("reference-date", app.warning[0].value)

    def test_unsupported_and_api_error(self):
        with patch("network_sql.ui.generate_sql", return_value="UNSUPPORTED"):
            app = self.start()
            app.text_area[0].input("Which interfaces are overloaded?").run()
            app.button[0].click().run()
            self.assertEqual(len(app.button), 1)
        with patch("network_sql.ui.generate_sql", side_effect=ValueError("Model service returned HTTP 429")):
            app.button[0].click().run()
            self.assertIn("429", app.warning[0].value)
            self.assertFalse(app.exception)

    def test_write_attempt_is_rejected(self):
        with patch("network_sql.ui.generate_sql", return_value="DELETE FROM devices;"):
            app = self.start()
            app.text_area[0].input("Count devices").run()
            app.button[0].click().run()
            app.button[1].click().run()
            self.assertIn("rejected", app.error[0].value)
            self.assertFalse(app.exception)


class WorkspaceTests(unittest.TestCase):
    def test_data_preview_uses_no_model_and_switches_tables(self):
        def page():
            from pathlib import Path
            from network_sql.database import seed
            from network_sql.views import explore_data
            seed(Path('data/network.db'))
            explore_data()
        with patch('network_sql.llm.generate_sql') as model:
            app = AppTest.from_function(page).run()
            self.assertFalse(app.exception)
            self.assertEqual([m.value for m in app.metric], ['3', '6', '1008'])
            self.assertEqual(len(app.dataframe[0].value), 3)
            app.selectbox[0].select('device_metrics').run()
            self.assertEqual(len(app.dataframe[0].value), 20)
            self.assertFalse(app.exception)
            model.assert_not_called()

    def test_reports_show_saved_failures_without_model_calls(self):
        def page():
            from network_sql.views import evaluation_results
            evaluation_results()
        with patch('network_sql.llm.generate_sql') as model:
            app = AppTest.from_function(page).run()
            self.assertFalse(app.exception)
            self.assertEqual(app.metric[0].value, '5/5')
            app.checkbox[0].check().run()
            self.assertEqual(len(app.expander), 0)
            app.selectbox[0].select('Challenge baseline').run()
            self.assertEqual(app.metric[0].value, '8/9')
            self.assertEqual(len(app.expander), 1)
            self.assertFalse(app.exception)
            model.assert_not_called()


if __name__ == "__main__":
    unittest.main()
