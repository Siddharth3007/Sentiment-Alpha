import unittest

import pandas as pd

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


if __name__ == "__main__":
    unittest.main()
