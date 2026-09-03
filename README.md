# Sentiment Alpha

Sentiment Alpha is a Python research project I built to test whether news and
earnings-call sentiment can be combined with simple technical signals. The current
case study uses AAPL. This is a backtesting project, not a live trading system.

## Scope

| Field | Value |
|---|---|
| Ticker | AAPL |
| Price/sentiment cutoff | 2024-11-27 |
| Deduplicated OOS period | 2020-07-14 to 2024-11-27 |
| OOS observations | 1,103 |
| Walk-forward folds | 22 |
| Qwen headline records | 25,629 dated / 25,048 unique |
| Training window | 132 trading days |
| Test window | Up to 56 trading days |
| Step | 50 trading days |
| Transaction cost | 5 bps per unit of turnover |

The compact input ends on 2024-11-27, and `run_backtest.load_data` independently
enforces the same cutoff. The last test fold is partial so the OOS series can end at
the data boundary without using later prices.

## Main strategy

The reported strategy is implemented in `full_quantile_news_overlay.py`:

- Normal exposure: `+0.5` AAPL.
- Bad-news recovery: prior score below the training-window q25, with price above SMA
  and RSI above its calibrated threshold; increase exposure to `+1.0` for one return.
- Moderate positive-news short: score between training q67 and q84, with price below
  SMA and weak RSI; hold `-1.0` for one return.
- Strong positive-news short: score above training q84 with the same technical filter;
  hold `-1.0` for three returns.
- Analyst overlay: analyst-question sentiment above zero raises exposure to `+1.0` for
  three returns. News shorts retain priority.

Quantiles use only nonzero-news observations from the preceding training fold and are
frozen during its test fold. The overlay inherits each fold's SMA length and RSI
threshold from the base-strategy training calibration; those technical parameters are
not re-optimized for the overlay. News is lagged before signal formation, positions are
entered at the following close, and costs are deducted from daily returns before
metrics are calculated.

## Files

| Path | Purpose |
|---|---|
| `strategy.py` | Causal indicators, base signals, returns, and performance metrics |
| `run_backtest.py` | Rolling calibration and deduplicated OOS construction |
| `full_quantile_news_overlay.py` | Canonical FinBERT quantile strategy |
| `full_analyst_sentiment_overlay.py` | Fixed-threshold analyst overlay comparison |
| `quick_llm_news_test.py` | Small Qwen3-0.6B classifier diagnostic |
| `full_llm_quantile_comparison.py` | Full matched-period Qwen-versus-FinBERT comparison |
| `quick_short_*.py` | Development grids for short thresholds and holding periods |
| `data/` | Compact price/sentiment and earnings-call feature inputs |
| `results/` | Daily audit trails, summaries, thresholds, labels, and plots |
| `tests/` | Timing, leakage, threshold, and integration tests |

## Setup

For the base backtests:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

The local Qwen scripts also require:

```bash
pip install -r requirements-llm.txt
```

## Running the project

Run from the repository root:

```bash
python run_backtest.py
python full_core_overlay.py
python full_analyst_sentiment_overlay.py
python full_quantile_news_overlay.py
python -m pytest -q
```

The Qwen comparison requires the raw news CSV, which is not included here. The file
must contain `date` and `title` columns:

```bash
python full_llm_quantile_comparison.py --source /path/to/apple_news_data.csv
```

Inference is checkpointed by anonymized headline hash. If the model or prompt changes,
delete or rename `results/full_llm_qwen3_0_6b_label_cache.csv` before rerunning; the
cache key does not currently include the model or prompt version.

## Results

All figures below use the common 1,103-day endpoint. Strategy returns include modeled
transaction costs; buy-and-hold excludes an initial purchase cost. Sharpe and Sortino
use 252 trading days and a 4% annual risk-free rate.

| Metric | FinBERT news | FinBERT + analyst | Qwen + analyst | AAPL buy and hold |
|---|---:|---:|---:|---:|
| Total return | 232.23% | **257.05%** | 122.58% | 146.06% |
| CAGR | 31.56% | **33.75%** | 20.06% | 22.84% |
| Sharpe ratio | 1.435 | **1.505** | 0.854 | 0.721 |
| Sortino ratio | 2.284 | **2.403** | 1.170 | 1.088 |
| Maximum drawdown | 14.41% | **14.06%** | 22.05% | 31.31% |

Qwen3-0.6B labeled 73.0% of the headline records positive. Its matched-period Sharpe
was lower than FinBERT's. The paired Qwen-minus-FinBERT HAC test with the analyst
overlay returned `p=0.145`, so the difference was not statistically significant at
the 5% level.

The AAPL study is a historical development result, not an untouched validation. Signal
rules and overlay choices were influenced by earlier diagnostics on overlapping data.
Only seven earnings calls qualified for the analyst overlay. See `RESULTS.md` for the
classifier benchmark, statistical tests, and additional limitations.

## Data

`data/aapl_news_scores.csv` is a compact extraction of aligned AAPL prices and daily
FinBERT scores from Trading Strategy v1. `data/aapl_earnings_features.csv` is a compact
extraction of earnings-call features from Trading Strategy v2. The source projects were
read-only and were not modified. Raw headlines are not redistributed in this repository.
