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

