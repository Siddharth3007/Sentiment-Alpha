import unittest

import pandas as pd

from quick_analyst_sentiment_overlay import add_analyst_long_overrides
from quick_earnings_integration import add_earnings_overrides


class EarningsIntegrationTests(unittest.TestCase):
    def test_bullish_call_enters_after_first_post_call_close(self):
        dates = pd.Series(pd.date_range("2024-01-03", periods=7, freq="B"))
        baseline = pd.Series([0.5] * len(dates))
        earnings = pd.DataFrame({
            "date": [pd.Timestamp("2024-01-03")],
            "sue": [1.0],
            "qa_sentiment": [0.2],
            "executive_sentiment": [0.3],
        })

        positions, events = add_earnings_overrides(baseline, dates, earnings)

        self.assertEqual(positions.tolist(), [0.5, 0.5, 1.0, 1.0, 1.0, 0.5, 0.5])
        self.assertEqual(events[0]["first_post_call_close"], "2024-01-04")
        self.assertEqual(events[0]["first_return_date"], "2024-01-05")

    def test_mixed_signs_do_not_override(self):
        dates = pd.Series(pd.date_range("2024-01-03", periods=5, freq="B"))
        baseline = pd.Series([0.5] * len(dates))
        earnings = pd.DataFrame({
            "date": [pd.Timestamp("2024-01-03")],
            "sue": [1.0],
            "qa_sentiment": [-0.2],
            "executive_sentiment": [0.3],
        })

        positions, events = add_earnings_overrides(baseline, dates, earnings)

        self.assertEqual(positions.tolist(), baseline.tolist())
        self.assertEqual(events, [])

    def test_analyst_long_respects_news_short_priority(self):
        dates = pd.Series(pd.date_range("2024-01-03", periods=7, freq="B"))
        baseline = pd.Series([0.5, 0.5, 0.5, -1.0, 0.5, 0.5, 0.5])
        earnings = pd.DataFrame({
            "date": [pd.Timestamp("2024-01-03")],
            "analyst_sentiment": [0.10],
        })

        positions, events = add_analyst_long_overrides(
            baseline, dates, earnings, threshold=0.05, holding_days=3
        )

        self.assertEqual(positions.tolist(), [0.5, 0.5, 1.0, -1.0, 1.0, 0.5, 0.5])
        self.assertEqual(events[0]["long_days_after_short_priority"], 2)

    def test_analyst_threshold_is_strict(self):
        dates = pd.Series(pd.date_range("2024-01-03", periods=5, freq="B"))
        baseline = pd.Series([0.5] * len(dates))
        earnings = pd.DataFrame({
            "date": [pd.Timestamp("2024-01-03")],
            "analyst_sentiment": [0.05],
        })

        positions, events = add_analyst_long_overrides(
            baseline, dates, earnings, threshold=0.05, holding_days=1
        )

        self.assertEqual(positions.tolist(), baseline.tolist())
        self.assertEqual(events, [])


if __name__ == "__main__":
    unittest.main()
