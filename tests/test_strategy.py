import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from strategy import add_returns, make_signals
from run_backtest import DATA_END, load_data, run_walk_forward


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

    def test_loader_enforces_raw_news_end_date(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "prices.csv"
            pd.DataFrame(
                {
                    "date": [DATA_END, DATA_END + pd.Timedelta(days=1)],
                    "close": [100.0, 101.0],
                    "news_score": [0.2, 0.0],
                }
            ).to_csv(path, index=False)
            loaded = load_data(path)
        self.assertEqual(loaded["date"].tolist(), [DATA_END])

    def test_walk_forward_retains_a_partial_final_fold(self):
        dates = pd.bdate_range(end=DATA_END, periods=139)
        data = pd.DataFrame(
            {
                "date": dates,
                "close": [100.0 + index for index in range(len(dates))],
                "news_score": 0.0,
            }
        )
        windows, _, oos = run_walk_forward(data)
        self.assertEqual(len(windows), 1)
        self.assertEqual(len(oos), 7)
        self.assertEqual(oos["date"].max(), DATA_END)


if __name__ == "__main__":
    unittest.main()
