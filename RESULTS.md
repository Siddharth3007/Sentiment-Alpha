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

