"""Full-period test of the frozen analyst-only earnings long overlay."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from scipy import stats

from full_core_overlay import evaluate
from quick_analyst_sentiment_overlay import add_analyst_long_overrides, build_baseline
from strategy import performance_metrics


ANALYST_THRESHOLD = 0.0
HOLDING_DAYS = 3


def period_return(returns: pd.Series) -> float:
    return float((1 + returns).prod() - 1)


def main() -> None:
    root = Path(__file__).resolve().parent
    data = pd.read_csv(root / "results/oos_daily.csv", parse_dates=["date"])
    earnings = pd.read_csv(root / "data/aapl_earnings_features.csv", parse_dates=["date"])
    earnings = earnings[
        earnings["date"].between(data["date"].min(), data["date"].max())
    ].copy()

    baseline_positions = build_baseline(data)
    analyst_positions, events = add_analyst_long_overrides(
        baseline_positions,
        data["date"],
        earnings,
        threshold=ANALYST_THRESHOLD,
        holding_days=HOLDING_DAYS,
    )

    baseline_returns, baseline_turnover, baseline_metrics = evaluate(
        data, baseline_positions
    )
    analyst_returns, analyst_turnover, analyst_metrics = evaluate(
        data, analyst_positions
    )
    benchmark_metrics = performance_metrics(data["market_return"])

    for event in events:
        event_start = pd.Timestamp(event["first_return_date"])
        matching_rows = data.index[data["date"].eq(event_start)]
        if len(matching_rows):
            start = int(matching_rows[0])
            stop = start + event["scheduled_holding_days"]
            event["incremental_simple_return_vs_baseline"] = float(
                (analyst_returns.iloc[start:stop] - baseline_returns.iloc[start:stop]).sum()
            )

    comparison = pd.DataFrame({
        "date": data["date"],
        "analyst_return": analyst_returns,
        "baseline_return": baseline_returns,
        "market_return": data["market_return"],
    })
    comparison["segment"] = "other"
    comparison.loc[comparison["date"] < pd.Timestamp("2022-01-01"), "segment"] = (
        "pre_selection_2020_2021"
    )
    comparison.loc[
        comparison["date"].between("2022-01-01", "2024-12-31"), "segment"
    ] = "parameter_selection_2022_2024"
    comparison.loc[comparison["date"] > pd.Timestamp("2024-12-31"), "segment"] = (
        "post_selection_2025_partial"
    )
    segment_results = {}
    for segment, rows in comparison.groupby("segment", sort=False):
        segment_results[segment] = {
            "start": rows["date"].min().date().isoformat(),
            "end": rows["date"].max().date().isoformat(),
            "observations": int(len(rows)),
            "analyst_overlay_return": period_return(rows["analyst_return"]),
            "baseline_return": period_return(rows["baseline_return"]),
            "aapl_return": period_return(rows["market_return"]),
        }

    daily_increment = analyst_returns - baseline_returns
    t_stat, p_value = stats.ttest_1samp(daily_increment, 0.0, nan_policy="omit")
    summary = {
        "period": {
            "start": data["date"].min().date().isoformat(),
            "end": data["date"].max().date().isoformat(),
            "observations": int(len(data)),
        },
        "frozen_rule": {
            "normal_position": 0.5,
            "analyst_signal": "analyst_sentiment > 0",
            "signal_position": 1.0,
            "holding_days": HOLDING_DAYS,
            "executive_sentiment_used": False,
            "sue_used": False,
            "news_shorts_have_priority": True,
            "execution": "Enter at first post-call close; earn returns beginning next close",
            "transaction_cost_bps_per_unit_turnover": 5.0,
        },
        "earnings_calls_available": int(len(earnings)),
        "qualifying_calls": int(len(events)),
        "events": events,
        "core_news_plus_analyst": analyst_metrics,
        "core_news_baseline": baseline_metrics,
        "aapl_buy_and_hold": benchmark_metrics,
        "segment_results": segment_results,
        "paired_daily_increment_test_vs_baseline": {
            "t_statistic": float(t_stat),
            "p_value_two_sided": float(p_value),
        },
        "warning": (
            "The rule was selected on 2022-2024 data. The full period overlaps that "
            "selection window and is not independent validation."
        ),
    }

    output = data[["date", "market_return"]].copy()
    output["baseline_position"] = baseline_positions
    output["baseline_turnover"] = baseline_turnover
    output["baseline_return"] = baseline_returns
    output["baseline_equity"] = (1 + baseline_returns).cumprod()
    output["analyst_position"] = analyst_positions
    output["analyst_turnover"] = analyst_turnover
    output["analyst_return"] = analyst_returns
    output["analyst_equity"] = (1 + analyst_returns).cumprod()
    output["benchmark_equity"] = (1 + output["market_return"]).cumprod()

    results = root / "results"
    output.to_csv(results / "full_analyst_sentiment_overlay_daily.csv", index=False)
    (results / "full_analyst_sentiment_overlay_summary.json").write_text(
        json.dumps(summary, indent=2)
    )

    plt.figure(figsize=(11, 6))
    plt.plot(
        output["date"], output["analyst_equity"],
        label="Core + news + analyst overlay", linewidth=2,
    )
    plt.plot(output["date"], output["baseline_equity"], label="Core + news baseline")
    plt.plot(
        output["date"], output["benchmark_equity"],
        label="AAPL buy & hold", alpha=0.75,
    )
    plt.title("Full walk-forward history: frozen analyst-only earnings overlay")
    plt.ylabel("Growth of $1")
    plt.grid(alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(results / "full_analyst_sentiment_overlay_equity.png", dpi=160)
    plt.close()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
