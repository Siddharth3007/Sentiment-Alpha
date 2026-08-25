"""Full-period FinBERT overlay with training-only nonzero-news quantiles."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from scipy import stats

from full_core_overlay import evaluate
from quick_analyst_sentiment_overlay import add_analyst_long_overrides
from quick_core_overlay import build_overlay_positions
from run_backtest import STEP, TRAIN_WINDOW, load_data
from strategy import performance_metrics


BAD_QUANTILE = 0.25
MODERATE_QUANTILE = 0.67
STRONG_QUANTILE = 0.84
ANALYST_THRESHOLD = 0.0
ANALYST_HOLDING_DAYS = 3


def nonzero_news_thresholds(scores: pd.Series) -> dict[str, float | int]:
    """Calculate signal cutoffs from news days only."""
    nonzero = pd.to_numeric(scores, errors="coerce").dropna()
    nonzero = nonzero[nonzero.ne(0)]
    if nonzero.empty:
        raise ValueError("Training window contains no nonzero-news days")
    return {
        "nonzero_news_days": int(len(nonzero)),
        "bad_threshold": float(nonzero.quantile(BAD_QUANTILE)),
        "moderate_threshold": float(nonzero.quantile(MODERATE_QUANTILE)),
        "strong_threshold": float(nonzero.quantile(STRONG_QUANTILE)),
    }


def attach_training_thresholds(
    oos: pd.DataFrame, source: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Attach each retained OOS row's own fold-specific training quantiles."""
    result = oos.copy()
    threshold_rows: list[dict] = []
    for window_id in sorted(result["window"].astype(int).unique()):
        train_start = (window_id - 1) * STEP
        train_end = train_start + TRAIN_WINDOW
        training = source.iloc[train_start:train_end]
        values = nonzero_news_thresholds(training["news_score"])
        threshold_rows.append(
            {
                "window": window_id,
                "train_start": training.iloc[0]["date"],
                "train_end": training.iloc[-1]["date"],
                **values,
            }
        )
    thresholds = pd.DataFrame(threshold_rows)
    result = result.merge(thresholds, on="window", how="left", validate="many_to_one")
    return result, thresholds


def build_quantile_positions(data: pd.DataFrame) -> tuple[pd.Series, dict[str, pd.Series]]:
    """Apply adaptive thresholds while preserving the existing overlay timing."""
    lagged_news = data["news_score"].shift(1)
    has_lagged_news = lagged_news.ne(0) & lagged_news.notna()
    long_filter = (data["close"] > data["sma"]) & (
        data["rsi"] > data["rsi_threshold"]
    )
    short_filter = (data["close"] < data["sma"]) & (
        data["rsi"] < (100 - data["rsi_threshold"])
    )
    bad_events = (
        has_lagged_news
        & (lagged_news < data["bad_threshold"])
        & long_filter
    )
    moderate_events = (
        has_lagged_news
        & (lagged_news > data["moderate_threshold"])
        & (lagged_news <= data["strong_threshold"])
        & short_filter
    )
    strong_events = (
        has_lagged_news
        & (lagged_news > data["strong_threshold"])
        & short_filter
    )
    positions = build_overlay_positions(bad_events, moderate_events, strong_events)
    return positions, {
        "bad": bad_events,
        "moderate": moderate_events,
        "strong": strong_events,
    }


def metric_with_position_counts(metrics: dict, positions: pd.Series) -> dict:
    enriched = dict(metrics)
    enriched.update(
        {
            "days_at_core_0.5": int(positions.eq(0.5).sum()),
            "days_at_long_1.0": int(positions.eq(1.0).sum()),
            "days_at_short_minus_1.0": int(positions.eq(-1.0).sum()),
        }
    )
    return enriched


def main() -> None:
    root = Path(__file__).resolve().parent
    source = load_data(root / "data/aapl_news_scores.csv")
    oos = pd.read_csv(root / "results/oos_daily.csv", parse_dates=["date"])
    data, thresholds = attach_training_thresholds(oos, source)

    news_positions, events = build_quantile_positions(data)
    news_returns, news_turnover, news_metrics = evaluate(data, news_positions)
    news_metrics = metric_with_position_counts(news_metrics, news_positions)

    earnings = pd.read_csv(
        root / "data/aapl_earnings_features.csv", parse_dates=["date"]
    )
    earnings = earnings[
        earnings["date"].between(data["date"].min(), data["date"].max())
    ].copy()
    analyst_positions, analyst_events = add_analyst_long_overrides(
        news_positions,
        data["date"],
        earnings,
        threshold=ANALYST_THRESHOLD,
        holding_days=ANALYST_HOLDING_DAYS,
    )
    analyst_returns, analyst_turnover, analyst_metrics = evaluate(
        data, analyst_positions
    )
    analyst_metrics = metric_with_position_counts(analyst_metrics, analyst_positions)
    benchmark_metrics = performance_metrics(data["market_return"])

    fixed_news_summary = json.loads(
        (root / "results/full_core_overlay_summary.json").read_text()
    )
    fixed_analyst_summary = json.loads(
        (root / "results/full_analyst_sentiment_overlay_summary.json").read_text()
    )
    fixed_daily = pd.read_csv(
        root / "results/full_analyst_sentiment_overlay_daily.csv"
    )
    news_increment = news_returns - fixed_daily["baseline_return"]
    analyst_increment = analyst_returns - fixed_daily["analyst_return"]
    news_t, news_p = stats.ttest_1samp(news_increment, 0.0, nan_policy="omit")
    analyst_t, analyst_p = stats.ttest_1samp(
        analyst_increment, 0.0, nan_policy="omit"
    )

    threshold_summary = {}
    for column in ("nonzero_news_days", "bad_threshold", "moderate_threshold", "strong_threshold"):
        threshold_summary[column] = {
            "min": float(thresholds[column].min()),
            "median": float(thresholds[column].median()),
            "max": float(thresholds[column].max()),
        }

    summary = {
        "period": {
            "start": data["date"].min().date().isoformat(),
            "end": data["date"].max().date().isoformat(),
            "observations": int(len(data)),
            "walk_forward_windows": int(len(thresholds)),
        },
        "adaptive_rule": {
            "threshold_population": "nonzero-news days in the fold's 132-day training window",
            "bad_news": "score below training 25th percentile",
            "moderate_good_news": "training 67th percentile < score <= training 84th percentile",
            "very_good_news": "score above training 84th percentile",
            "thresholds_frozen_within_each_test_fold": True,
            "normal_position": 0.5,
            "bad_news_position": 1.0,
            "bad_news_holding_days": 1,
            "moderate_short_position": -1.0,
            "moderate_short_holding_days": 1,
            "strong_short_position": -1.0,
            "strong_short_holding_days": 3,
            "technical_filters": "existing fold-specific SMA and RSI",
            "transaction_cost_bps_per_unit_turnover": 5.0,
        },
        "training_threshold_distribution": threshold_summary,
        "events": {
            "bad_news": int(events["bad"].sum()),
            "moderate_good_news": int(events["moderate"].sum()),
            "very_good_news": int(events["strong"].sum()),
        },
        "adaptive_core_news": news_metrics,
        "adaptive_core_news_plus_analyst": analyst_metrics,
        "analyst_qualifying_calls": int(len(analyst_events)),
        "fixed_threshold_comparisons": {
            "fixed_core_news": fixed_news_summary["core_plus_overlay"],
            "fixed_core_news_plus_analyst": fixed_analyst_summary[
                "core_news_plus_analyst"
            ],
        },
        "paired_daily_increment_tests_vs_fixed": {
            "adaptive_core_news": {
                "t_statistic": float(news_t),
                "p_value_two_sided": float(news_p),
            },
            "adaptive_core_news_plus_analyst": {
                "t_statistic": float(analyst_t),
                "p_value_two_sided": float(analyst_p),
            },
        },
        "aapl_buy_and_hold": benchmark_metrics,
        "warning": (
            "Historical development-period comparison. Quantile levels were proposed "
            "after examining the original score distribution and are not an untouched validation."
        ),
    }

    output = data[
        [
            "date", "close", "market_return", "news_score", "window",
            "sma", "rsi", "sma_window", "rsi_threshold",
            "bad_threshold", "moderate_threshold", "strong_threshold",
        ]
    ].copy()
    output["adaptive_news_position"] = news_positions
    output["adaptive_news_turnover"] = news_turnover
    output["adaptive_news_return"] = news_returns
    output["adaptive_news_equity"] = (1 + news_returns).cumprod()
    output["adaptive_analyst_position"] = analyst_positions
    output["adaptive_analyst_turnover"] = analyst_turnover
    output["adaptive_analyst_return"] = analyst_returns
    output["adaptive_analyst_equity"] = (1 + analyst_returns).cumprod()
    output["benchmark_equity"] = (1 + output["market_return"]).cumprod()

    results = root / "results"
    output.to_csv(results / "full_quantile_news_overlay_daily.csv", index=False)
    thresholds.to_csv(results / "full_quantile_news_thresholds.csv", index=False)
    (results / "full_quantile_news_overlay_summary.json").write_text(
        json.dumps(summary, indent=2)
    )

    plt.figure(figsize=(11, 6))
    plt.plot(
        output["date"], output["adaptive_analyst_equity"],
        label="Adaptive news + analyst", linewidth=2,
    )
    plt.plot(
        output["date"], output["adaptive_news_equity"],
        label="Adaptive news",
    )
    plt.plot(
        output["date"], output["benchmark_equity"],
        label="AAPL buy & hold", alpha=0.75,
    )
    plt.title("Training-only nonzero-news quantile thresholds")
    plt.ylabel("Growth of $1")
    plt.grid(alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(results / "full_quantile_news_overlay_equity.png", dpi=160)
    plt.close()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
