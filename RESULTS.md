# Results

## Evaluation scope

All primary comparisons use the same deduplicated walk-forward period:

- Ticker: AAPL
- OOS dates: 2020-07-14 to 2024-11-27
- OOS observations: 1,103
- Walk-forward folds: 22
- Training window: 132 trading days
- Test window: up to 56 trading days; the last fold is partial
- Transaction cost: 5 bps per unit of turnover
- Annual risk-free rate used for Sharpe and Sortino calculations: 4%

November 27, 2024 is a hard data boundary. Later price rows in the source extraction
have zero-filled news scores and are not used.

## Strategy comparison

| Construction | Total return | CAGR | Sharpe | Sortino | Max drawdown | Turnover |
|---|---:|---:|---:|---:|---:|---:|
| Base sparse long/short | 79.17% | 14.25% | 0.883 | 0.833 | 12.71% | 296.0 |
| Fixed core + news | 242.50% | 32.48% | 1.438 | 2.264 | **10.71%** | 258.5 |
| Fixed core + news + analyst | **264.86%** | **34.41%** | 1.497 | 2.361 | **10.34%** | 265.5 |
| Adaptive FinBERT news | 232.23% | 31.56% | 1.435 | 2.284 | 14.41% | 246.5 |
| Adaptive FinBERT news + analyst | 257.05% | 33.75% | **1.505** | **2.403** | 14.06% | 252.5 |
| AAPL buy and hold | 146.06% | 22.84% | 0.721 | 1.088 | 31.31% | n/a |

The adaptive construction is the canonical specification. Its news thresholds are the
25th, 67th, and 84th percentiles of nonzero-news scores in each training fold. The
numeric cutoffs are frozen during the following test fold. The analyst overlay increases
exposure from 50% to 100% for three returns after a call with positive analyst-question
sentiment; news shorts retain priority.

The fixed-threshold construction produced a higher compounded return and lower maximum
drawdown, while the adaptive construction produced the highest Sharpe and Sortino after
the analyst overlay. Paired daily adaptive-versus-fixed tests returned p-values of 0.884
for news alone and 0.914 with the analyst overlay, providing no evidence that either
threshold method is statistically superior.

## Earnings-call overlay

Eighteen calls were available during the OOS period and seven satisfied
`analyst_sentiment > 0`. Executive sentiment and earnings surprise are not used in the
reported analyst overlay. For the fixed-threshold strategy, the analyst overlay raised
total return from 242.50% to 264.86% and Sharpe from 1.438 to 1.497. Its paired daily
increment test produced p=0.106, which is not significant at the 5% level.

The rule was selected after examining overlapping 2022–2024 data. The earnings result
is therefore a development diagnostic rather than independent validation.

## Qwen3-0.6B versus FinBERT

Qwen classified 25,629 dated headline records representing 25,048 unique anonymized
headlines. Both classifiers used model-specific training-only q25/q67/q84 thresholds;
all dates, technical filters, positions, analyst signals, and costs were held constant.

| Metric | Qwen news | FinBERT news | Qwen + analyst | FinBERT + analyst |
|---|---:|---:|---:|---:|
| Total return | 108.39% | **232.23%** | 122.58% | **257.05%** |
| CAGR | 18.26% | **31.56%** | 20.06% | **33.75%** |
| Sharpe | 0.783 | **1.435** | 0.854 | **1.505** |
| Sortino | 1.066 | **2.284** | 1.170 | **2.403** |
| Max drawdown | 22.03% | **14.41%** | 22.05% | **14.06%** |

Qwen labels were 18,720 positive, 5,641 negative, and 1,268 neutral. The 73.0%
positive rate made its daily scores strongly bullish: only 43 of 1,092 news days had a
negative aggregate score, and the median fold's q25 cutoff was still positive at 0.417.
The constrained-label implementation agreed with ordinary generated labels on 332 of
333 pilot headlines, so output parsing does not explain the imbalance.

Newey-West/HAC tests of paired Qwen-minus-FinBERT daily returns produced p=0.150 for
news alone and p=0.145 with the analyst overlay. FinBERT was economically and
numerically better in this sample, but the paired difference is not significant at 5%.

## Limitations

- This is a one-ticker historical case study and does not establish cross-sectional
  generalization.
- Strategy construction and parameter choices were influenced by diagnostics on the
  same broad history; the reported period is not an untouched final holdout.
- Early training folds contain relatively few nonzero-news days, making their quantile
  estimates unstable.
- The cost model excludes variable spreads, market impact, short-borrow fees, dividends,
  and interest on unused cash.
- Qwen3-0.6B is a small local proxy, not Qwen3-4B-Instruct-2507. Model pretraining may
  contain historical event knowledge despite entity anonymization.
- The earnings overlay is based on only seven qualifying calls.

## Audit artifacts

| File | Contents |
|---|---|
| `results/oos_daily.csv` | Deduplicated base walk-forward observations |
| `results/window_results.csv` | Per-fold calibration and test metadata |
| `results/full_quantile_news_overlay_daily.csv` | Canonical FinBERT positions and returns |
| `results/full_quantile_news_thresholds.csv` | Training-only thresholds by fold |
| `results/full_llm_quantile_daily.csv` | Matched Qwen and FinBERT daily comparison |
| `results/full_llm_quantile_labels.csv` | Dated Qwen labels keyed by headline hash |
| `results/full_llm_quantile_summary.json` | Classifier comparison metrics and HAC tests |
