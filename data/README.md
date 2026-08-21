# Data provenance

`aapl_news_scores.csv` contains only the three fields required by this backtest:

- `date`
- `close`
- `news_score`

It was copied into this fresh repository from the already aligned simulation dataset in Trading Strategy v1. The news score is the existing daily FinBERT score; this repository does not rerun the language model. Source repositories were read only and were not modified.

`aapl_earnings_features.csv` is a compact read-only extraction from Trading Strategy v2's generated earnings workbook. It includes the call date, SUE, SUR, overall Q&A sentiment, analyst sentiment, executive sentiment, and tone dispersion for 56 Apple calls from 2011–2024.

