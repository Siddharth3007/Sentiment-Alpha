# Walk-Forward Backtest Results

## Conclusion

The repaired news-plus-technical strategy produced a positive out-of-sample result and materially reduced volatility and drawdown, but it did not beat AAPL buy-and-hold on absolute return. The evidence is not strong enough to claim statistically significant excess return.

## Deduplicated out-of-sample results

Period: 2020-07-14 to 2025-04-30  
Unique test days: 1,206  
Walk-forward windows: 24

| Metric | Strategy, net | Strategy, gross | AAPL buy & hold |
|---|---:|---:|---:|
| Total return | 80.70% | 109.67% | 122.57% |
| CAGR | 13.16% | 16.73% | 18.20% |
| Sharpe ratio | 0.83 | 1.11 | 0.57 |
| Annualized volatility | 10.79% | 10.83% | 30.01% |
| Maximum drawdown | 12.71% | 9.87% | 33.43% |
| Sortino ratio | 0.75 | 0.81 | 0.84 |

The strategy was invested on 186 of 1,206 days (15.42% exposure). Its active-day hit rate was 57.53%. It generated 298 units of turnover; the assumed cost was 5 basis points per unit of turnover.

## Window consistency

- 18 of 24 windows had positive strategy returns.
- 12 of 24 windows beat AAPL in the same window.
- Mean strategy window return was 2.84%; mean AAPL window return was 4.72%.
- The paired daily excess-return test gave a two-sided p-value of 0.574, so excess performance is not statistically significant at conventional levels.

## Interpretation

The signal behaved more like a low-exposure risk-control strategy than an AAPL replacement. It captured a smoother upward path and avoided much of AAPL's drawdown, but its low market exposure caused it to miss a large portion of AAPL's rally. Trading costs were consequential because most sentiment events created short-lived positions.

This is a historical research result, not evidence of a deployable trading edge. It excludes slippage beyond the stated cost, short-borrow fees, taxes, intraday execution uncertainty, and any retraining of the underlying FinBERT news scores.

## Quick short-only holding-period diagnostic

Period: 2024-01-01 through 2025-04-30. This reuses previously examined out-of-sample data and is therefore a development diagnostic, not a fresh holdout.

| Metric | One-day short | Three-day short | AAPL buy & hold |
|---|---:|---:|---:|
| Total return | 5.34% | 0.68% | 10.37% |
| CAGR | 4.01% | 0.51% | 7.75% |
| Sharpe ratio | 0.02 | -0.29 | 0.26 |
| Maximum drawdown | 4.18% | 12.30% | 33.43% |
| Exposure | 7.81% | 18.02% | 100.00% |
| Entries | 18 | 14 | n/a |

The fixed three-day extension worsened both return and drawdown. For this recent compact period, the original one-day short is the better rule. A future exit test should use a condition-based exit rather than automatically extending every news event.

### Small parameter grid

The same period was tested across positive-news thresholds of 0.10, 0.20 and 0.30 and holding periods of 1, 2, 3 and 5 trading days. All returns include five basis points per unit of turnover.

| Sentiment threshold | 1 day | 2 days | 3 days | 5 days |
|---:|---:|---:|---:|---:|
| 0.10 | 3.84% | -1.24% | 0.24% | 3.41% |
| 0.20 | **5.34%** | 3.49% | 0.68% | -5.11% |
| 0.30 | 2.14% | 1.81% | 4.92% | -3.29% |

The original threshold of 0.20 with a one-day hold remained best. This result supports retaining the baseline for now, but it does not validate the parameters because the grid was evaluated on previously examined development data.

### Tiered short rule

The following combined rule was then tested over the same period:

- `0.20 < lagged sentiment <= 0.30`: short for one trading day.
- `lagged sentiment > 0.30`: short for three trading days.

| Metric | Tiered rule | Baseline 0.20/1-day | AAPL buy & hold |
|---|---:|---:|---:|
| Total return | **7.86%** | 5.34% | 10.37% |
| CAGR | **5.89%** | 4.01% | 7.75% |
| Sharpe ratio | **0.26** | 0.02 | 0.26 |
| Maximum drawdown | 4.31% | **4.18%** | 33.43% |
| Exposure | 12.91% | 7.81% | 100.00% |
| Entries | 15 | 18 | n/a |

The tiered rule improved return and Sharpe while leaving drawdown nearly unchanged. It used 14 moderate-sentiment events and 11 strong-sentiment events. This is the strongest short-only development rule tested so far, but it still requires validation on a genuinely untouched period.

### 50% AAPL core plus news overlay

The next diagnostic used a permanent 50% AAPL position, increased exposure to 100% for a one-day negative-news recovery signal, and allowed the tiered short rule to override and flip exposure to -100%. After a short expired, exposure returned to 50%. The uninvested portion earned 0%.

| Metric | 50% core + overlay | Passive 50% AAPL | AAPL buy & hold |
|---|---:|---:|---:|
| Total return | **24.04%** | 6.63% | 10.37% |
| CAGR | **17.71%** | 4.98% | 7.75% |
| Sharpe ratio | **0.82** | 0.13 | 0.26 |
| Sortino ratio | **1.22** | 0.18 | 0.36 |
| Maximum drawdown | 18.01% | **18.01%** | 33.43% |
| Annualized volatility | 16.72% | 15.14% | 30.27% |

The strategy spent 278 days at +50%, 12 days at +100%, and 43 days at -100%. It used 56 units of turnover after direct position flips and five-basis-point costs. This construction produced the strongest return and risk-adjusted result in the small-period diagnostics, but it was designed using the same development period and requires untouched validation.

## Full-period 50% core plus news overlay

The core-plus-overlay rule was frozen and applied to all 1,206 deduplicated walk-forward test days from 2020-07-14 through 2025-04-30. The remaining cash earned 0%, and all position changes were charged five basis points per unit of turnover.

| Metric | Core + overlay | Original long/short | Tiered short-only | Passive 50% AAPL | AAPL buy & hold |
|---|---:|---:|---:|---:|---:|
| Total return | **230.00%** | 80.70% | 53.48% | 57.35% | 122.57% |
| CAGR | **28.34%** | 13.16% | 9.37% | 9.94% | 18.20% |
| Sharpe ratio | **1.24** | 0.83 | 0.57 | 0.44 | 0.57 |
| Sortino ratio | **1.91** | 0.75 | 0.41 | 0.64 | 0.84 |
| Maximum drawdown | 18.01% | 12.71% | **7.59%** | 18.01% | 33.43% |
| Annualized volatility | 18.19% | 10.79% | **9.44%** | 15.01% | 30.01% |

The strategy held +50% for 964 days, +100% for 90 days, and -100% for 152 days. Average gross exposure was 60.03%, average net exposure was 34.83%, and total turnover was 259.5 units. It produced positive calendar-period returns in 2020–2024 and lost 7.10% in the partial 2025 period, versus a 15.14% AAPL loss.

Although the compounded historical result beat AAPL, its paired daily excess-return p-value was 0.614 and therefore was not statistically significant. Moreover, the overlay design was influenced by the 2024–2025 subset and prior full-period diagnostics. The result is a historical development backtest, not an untouched validation.

## Small-window earnings-call integration

Period: 2022-01-01 through 2024-12-31. The test contained 12 Apple earnings calls and used the existing 50% core plus tiered-news overlay as its baseline. An earnings call overrode the news position for three trading days when all three signs agreed:

- Bullish: positive standardized unexpected earnings (`SUE`), positive overall Q&A sentiment, and positive executive sentiment; position +100%.
- Bearish: all three inputs negative; position -100%.

Calls were assumed to occur after the market close. The strategy entered at the first subsequent trading close, so it did not earn the immediate overnight reaction. Position changes cost five basis points per unit of turnover.

| Metric | Core + news + earnings | Core + news | AAPL buy & hold |
|---|---:|---:|---:|
| Total return | 102.21% | **110.68%** | 41.03% |
| CAGR | 26.57% | **28.32%** | 12.19% |
| Sharpe ratio | 1.25 | **1.35** | 0.41 |
| Sortino ratio | 1.96 | **2.22** | 0.62 |
| Maximum drawdown | **9.03%** | 10.71% | 31.31% |
| Annualized volatility | 16.80% | **16.51%** | 27.11% |

The earnings overlay did not improve return or risk-adjusted return. It reduced total return by 8.47 percentage points and Sharpe by 0.10, while improving maximum drawdown by 1.68 percentage points. Nine calls generated bullish overrides, none generated bearish overrides, and the remaining three generated no signal. Four overrides helped relative to the baseline and five hurt.

The largest failure followed the 2024-08-01 call and cost approximately 9.03 percentage points of simple return relative to the baseline during its override. Executive and overall Q&A sentiment were positive, but analyst sentiment was slightly negative. Analyst–management agreement is therefore a sensible next hypothesis, but adding that filter now would be a post-hoc adjustment rather than independent validation.

This is a compact development diagnostic with only 12 calls. It is useful for rejecting this first earnings rule, not for establishing a durable earnings-call edge.

## Analyst-only earnings long overlay

The earnings rule was simplified to use analyst-question sentiment only. Executive sentiment and SUE were ignored. On a qualifying call, exposure increased from the existing core/news position to +100%, while any active news short retained priority. The same conservative execution convention was used: enter at the first trading close after the call and earn returns beginning with the following close-to-close period.

Period: 2022-01-01 through 2024-12-31. All figures include five basis points per unit of turnover.

| Analyst threshold | Holding period | Qualifying calls | Total return | CAGR | Sharpe | Max drawdown |
|---:|---:|---:|---:|---:|---:|---:|
| > 0.00 | 1 day | 4 | 114.83% | 29.16% | 1.39 | 10.71% |
| > 0.00 | 3 days | 4 | **122.31%** | **30.65%** | **1.44** | **10.34%** |
| > 0.05 | 1 day | 1 | 113.29% | 28.85% | 1.37 | 10.71% |
| > 0.05 | 3 days | 1 | 113.93% | 28.98% | 1.38 | 10.71% |
| Core + news baseline | n/a | n/a | 110.68% | 28.32% | 1.35 | 10.71% |
| AAPL buy & hold | n/a | n/a | 41.03% | 12.19% | 0.41 | 31.31% |

The best tested construction—analyst sentiment above zero with a three-day hold—improved total return by 11.63 percentage points and Sharpe by 0.09 relative to the core/news baseline. All four qualifying calls contributed positively over their scheduled override periods: 2022-01-27, 2022-04-28, 2023-11-02, and 2024-02-01.

This is encouraging but extremely sparse evidence: only four of the 12 calls qualified, and the rule and parameters were examined on an already-used development window. The result supports testing analyst sentiment on the longer 2011–2024 call history; it does not yet validate the rule or the three-day holding period.

## Full-window analyst-only overlay

The small-window winner was frozen and applied unchanged to all 1,206 deduplicated walk-forward observations from 2020-07-14 through 2025-04-30:

- Normal position: +50%.
- Analyst-question sentiment > 0: increase to +100% for three trading days.
- Executive sentiment and SUE: unused.
- Existing news shorts: highest priority and remain at -100%.
- Trading cost: five basis points per unit of turnover.

| Metric | Core + news + analyst | Core + news baseline | AAPL buy & hold |
|---|---:|---:|---:|
| Total return | **251.54%** | 230.00% | 122.57% |
| CAGR | **30.04%** | 28.34% | 18.20% |
| Sharpe ratio | **1.30** | 1.24 | 0.57 |
| Sortino ratio | **2.00** | 1.91 | 0.84 |
| Maximum drawdown | 18.01% | **18.01%** | 33.43% |
| Annualized volatility | 18.46% | **18.19%** | 30.01% |

Eighteen calls were available and seven had positive analyst sentiment. Six of the seven analyst overrides helped relative to the baseline during their scheduled periods; the 2021-04-28 call hurt. The overlay added 21.54 percentage points of compounded full-period return, with slightly higher volatility and unchanged maximum drawdown.

The segment breakdown is important:

| Segment | Analyst overlay | Baseline | AAPL |
|---|---:|---:|---:|
| Pre-selection: 2020-07-14 to 2021-12-31 | 70.21% | 68.61% | 85.98% |
| Parameter-selection window: 2022–2024 | 122.31% | 110.68% | 41.03% |
| Partial 2025, no qualifying call | -7.10% | -7.10% | -15.14% |

The paired daily incremental-return test against the core/news baseline produced a two-sided p-value of 0.106. The improvement is therefore not statistically significant at the conventional 5% level. Most of the gain occurred in the 2022–2024 period used to select the rule; the earlier segment improved only modestly. This remains a development result rather than independent validation.

## Small-window local-LLM news diagnostic

Qwen3-0.6B replaced only the FinBERT headline classifier over October 1–November 27,
2024. The 334 source headlines were anonymized, classified locally with deterministic
decoding and no retrieval, and aggregated with the original net-score formula. The
strategy thresholds, technical filters, holding periods, execution lag, and transaction
costs were unchanged.

| Metric | Qwen3-0.6B overlay | FinBERT overlay | Passive 50% AAPL | AAPL buy & hold |
|---|---:|---:|---:|---:|
| Total return | 2.57% | **3.34%** | 0.46% | 0.83% |
| Sharpe ratio | 0.82 | **1.10** | -0.09 | 0.14 |
| Maximum drawdown | **3.85%** | **3.85%** | 3.09% | 6.12% |

The Qwen score had only 0.30 Pearson correlation with the FinBERT score. It labeled
280 of 334 headlines positive, 43 negative, and 11 neutral, producing an implausibly
bullish average daily score of 0.63 versus 0.05 for FinBERT. It generated no negative-
news recovery events and converted most technical short setups into strong shorts.

This run demonstrates that the LLM pipeline works, but **does not support replacing
FinBERT with Qwen3-0.6B**. The small model's label calibration is poor, and the 42-day
window is both short and previously observed. A credible next experiment requires the
4B instruct model, a calibration set labeled independently of returns, frozen prompts
and thresholds, and a later untouched test period.

## Training-only nonzero-news quantile thresholds

The fixed FinBERT thresholds were replaced with fold-specific values calculated only
from nonzero-news days in each 132-day training window:

- Bad news: below the training 25th percentile.
- Moderate good news: above the 67th and at or below the 84th percentile.
- Very good news: above the 84th percentile.

The percentile definitions remained fixed while their numerical score cutoffs changed
between walk-forward folds. All technical filters, position rules, timing conventions,
analyst-call rules, and five-basis-point transaction costs were unchanged.

| Metric | Adaptive core + news | Fixed core + news | Adaptive + analyst | Fixed + analyst | AAPL |
|---|---:|---:|---:|---:|---:|
| Total return | 220.10% | **230.00%** | 244.02% | **251.54%** | 122.57% |
| CAGR | 27.52% | **28.34%** | 29.46% | **30.04%** | 18.20% |
| Sharpe ratio | 1.235 | **1.243** | **1.301** | 1.299 | 0.573 |
| Sortino ratio | **1.914** | 1.913 | **2.024** | 2.004 | 0.841 |
| Maximum drawdown | 18.01% | 18.01% | 18.01% | 18.01% | 33.43% |
| Turnover | **247.5** | 259.5 | **253.5** | 266.5 | n/a |

Adaptive thresholds slightly reduced returns and turnover. The analyst version's
Sharpe increased by only 0.002, which is economically negligible. Daily incremental-
return tests versus the fixed versions produced p-values of 0.884 for core/news and
0.914 with the analyst overlay, providing no evidence that either construction was
superior.

Threshold stability was poor in the earliest folds because the source corpus contained
only 14–81 nonzero-news days in the first five 132-day windows. Later windows generally
contained 108–126 news days and produced much more plausible cutoffs. This exact test
therefore answers the requested quantile specification but also confirms that an
expanding-window or minimum-sample fallback would be required for a production design.
