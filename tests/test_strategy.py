import unittest

import pandas as pd

from strategy import add_returns, make_signals


class StrategyTests(unittest.TestCase):
    def test_news_is_lagged(self):
        dates = pd.date_range("2024-01-01", periods=40, freq="B")
        data = pd.DataFrame({
            "date": dates,
            "close": [100 + i for i in range(40)],
            "news_score": [0.0] * 30 + [-1.0] + [0.0] * 9,
        })
        result = make_signals(data, sma_window=10, rsi_threshold=40)
        self.assertEqual(result.loc[30, "signal"], 0)
        self.assertEqual(result.loc[31, "signal"], 1)

    def test_execution_uses_prior_signal(self):
        data = pd.DataFrame({"close": [100.0, 110.0, 121.0], "signal": [1, 0, 0]})
        result = add_returns(data, transaction_cost_bps=0)
        self.assertEqual(result.loc[0, "position"], 0)
        self.assertEqual(result.loc[1, "position"], 1)
        self.assertAlmostEqual(result.loc[1, "strategy_return"], 0.10)


if __name__ == "__main__":
    unittest.main()

