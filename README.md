# Sentiment Alpha

Point-in-time research infrastructure for evaluating equity strategies built from
financial-news sentiment, earnings-call sentiment, and technical state variables.
The repository contains an AAPL case study; it is a research backtester, not a live
trading system.

## Research boundary

| Field | Value |
|---|---|
| Ticker | AAPL |
| Price/sentiment cutoff | 2024-11-27 |
| Deduplicated OOS period | 2020-07-14 to 2024-11-27 |
| OOS observations | 1,103 |
| Walk-forward folds | 22 |
| Training window | 132 trading days |
| Test window | Up to 56 trading days |
| Step | 50 trading days |
| Transaction cost | 5 bps per unit of turnover |

The compact input ends on 2024-11-27, and `run_backtest.load_data` independently
enforces the same cutoff. The last test fold is partial so the OOS series can end at
the data boundary without using later prices.

## Canonical strategy

The primary reported construction is implemented in
`full_quantile_news_overlay.py`:

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
frozen during its test fold. SMA length and RSI threshold are also selected using
training data only. News is lagged before signal formation, positions are entered at
the following close, and costs are deducted from daily returns before metrics are
calculated.

## Repository layout

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

## Environment

Base backtests:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Local Qwen diagnostics additionally require:

```bash
pip install -r requirements-llm.txt
```

## Reproduce the canonical results

Run from the repository root:

```bash
python run_backtest.py
python full_core_overlay.py
python full_analyst_sentiment_overlay.py
python full_quantile_news_overlay.py
python -m pytest -q
```

The Qwen comparison requires the raw news CSV, which is not redistributed here. It
must contain `date` and `title` columns:

```bash
python full_llm_quantile_comparison.py --source /path/to/apple_news_data.csv
```

Inference is checkpointed by anonymized headline hash. If the model or prompt changes,
use a new cache rather than reusing labels produced by the previous configuration.

## Primary result

All figures below use the common 1,103-day endpoint and include modeled transaction
costs.

| Metric | FinBERT news + analyst | AAPL buy and hold |
|---|---:|---:|
| Total return | 257.05% | 146.06% |
| CAGR | 33.75% | 22.84% |
| Sharpe ratio | 1.505 | 0.721 |
| Sortino ratio | 2.403 | 1.088 |
| Maximum drawdown | 14.06% | 31.31% |

The AAPL study is a historical development result, not an untouched validation. Signal
rules and overlay choices were influenced by earlier diagnostics on overlapping data.
See `RESULTS.md` for the classifier benchmark, statistical tests, and limitations.

## Data provenance

`data/aapl_news_scores.csv` is a compact extraction of aligned AAPL prices and daily
FinBERT scores from Trading Strategy v1. `data/aapl_earnings_features.csv` is a compact
extraction of earnings-call features from Trading Strategy v2. The source projects were
read-only and were not modified.
