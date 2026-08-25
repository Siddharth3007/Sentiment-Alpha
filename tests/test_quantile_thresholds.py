import unittest

import pandas as pd

from full_quantile_news_overlay import nonzero_news_thresholds


class QuantileThresholdTests(unittest.TestCase):
    def test_zeros_are_excluded_from_threshold_population(self):
        scores = pd.Series([0.0, 0.0, -1.0, -0.5, 0.5, 1.0])
        actual = nonzero_news_thresholds(scores)
        expected = scores[scores.ne(0)]

        self.assertEqual(actual["nonzero_news_days"], 4)
        self.assertAlmostEqual(actual["bad_threshold"], expected.quantile(0.25))
        self.assertAlmostEqual(actual["moderate_threshold"], expected.quantile(0.67))
        self.assertAlmostEqual(actual["strong_threshold"], expected.quantile(0.84))

    def test_empty_nonzero_population_is_rejected(self):
        with self.assertRaises(ValueError):
            nonzero_news_thresholds(pd.Series([0.0, 0.0]))


if __name__ == "__main__":
    unittest.main()
