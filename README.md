# Sentiment Alpha

Point-in-time equity research infrastructure for testing news- and earnings-call-sentiment hypotheses with walk-forward validation.

This is a fresh repository created without modifying Trading Strategy v1 or v2.

## Strategy

The backtest repairs and lightly tightens the original construction:

- Long when the prior trading day's news score is below `-0.05`, AAPL is above its SMA, and RSI confirms positive momentum.
- Short when the prior trading day's news score is above `0.20`, AAPL is below its SMA, and RSI confirms negative momentum.
- News is lagged one trading day to prevent same-day news look-ahead.
- Signals formed at a close become positions for the following close-to-close return.
- Trading cost is 5 basis points per unit of position turnover.

The original RSI bug is corrected: thresholds are applied to RSI, not to AAPL's closing price.

## Walk-forward method

- 132 trading-day training window
- 56 trading-day testing window
- 50 trading-day step
- SMA grid: 10, 20, 30
- RSI threshold grid: 40, 45, 50, 55, 60
- Parameters maximize net annualized Sharpe on each training window
- The six overlapping days between adjacent test windows are deduplicated; the earliest out-of-sample prediction is retained

## Run

```bash
python run_backtest.py
python quick_earnings_integration.py
python quick_analyst_sentiment_overlay.py
python full_analyst_sentiment_overlay.py
python quick_llm_news_test.py
python -m unittest discover -s tests
```

The core walk-forward test uses a compact extraction of the existing aligned AAPL price and precomputed FinBERT daily news-score history. The two earnings diagnostic scripts use the compact AAPL earnings-call feature extraction in `data/aapl_earnings_features.csv`.

## Latest result

For the deduplicated out-of-sample period from 2020-07-14 through 2025-04-30:

- Net strategy return: 80.70%
- Net CAGR: 13.16%
- Net Sharpe ratio: 0.83
- Maximum drawdown: 12.71%
- AAPL buy-and-hold return: 122.57%
- AAPL Sharpe ratio: 0.57
- AAPL maximum drawdown: 33.43%

See `RESULTS.md` and the files under `results/` for the full audit trail.

### Latest core-plus-overlay construction

The frozen 50% AAPL core plus news overlay was subsequently evaluated over the full deduplicated walk-forward history. It returned 230.00%, versus 122.57% for AAPL, with an 18.01% maximum drawdown versus 33.43%. This is a historical development-period result rather than an untouched final validation.

### Analyst-only earnings overlay

The latest small-window diagnostic raises exposure from 50% to 100% using only positive analyst-question sentiment after earnings calls. News shorts retain priority. See `RESULTS.md` for the four threshold/holding-period comparisons and limitations.

The selected rule—analyst sentiment above zero with a three-day hold—is also applied unchanged by `full_analyst_sentiment_overlay.py` to the entire deduplicated 2020–2025 history.

`quick_llm_news_test.py` is an optional local-LLM diagnostic. It classifies anonymized
headlines with Qwen3-0.6B and compares the unchanged core/news strategy with the
existing FinBERT version over October 1–November 27, 2024. It requires `torch` and
`transformers`, and reads the original news CSV without modifying the source project.
