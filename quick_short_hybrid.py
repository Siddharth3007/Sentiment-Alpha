"""Test the tiered short holding rule against the one-day baseline."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from run_backtest import DATA_END
from strategy import performance_metrics


START = pd.Timestamp("2024-01-01")
END = DATA_END
COST_PER_TURNOVER = 5 / 10_000


def build_positions(event_holds: pd.Series) -> pd.Series:
    """Short after each event for its assigned number of subsequent returns."""
    positions = pd.Series(0, index=event_holds.index, dtype=int)
    for event_index, holding_days in event_holds[event_holds > 0].items():
        start = event_index + 1
        stop = min(start + int(holding_days), len(positions))
        if start < len(positions):
            positions.iloc[start:stop] = -1
    return positions


def evaluate(data: pd.DataFrame, event_holds: pd.Series) -> tuple[pd.DataFrame, dict]:
    positions = build_positions(event_holds)
    turnover = positions.diff().abs()
    turnover.iloc[0] = abs(positions.iloc[0])
    returns = positions * data["market_return"] - turnover * COST_PER_TURNOVER

    mask = data["date"].between(START, END)
    period = pd.DataFrame({
        "date": data.loc[mask, "date"],
        "position": positions[mask],
        "turnover": turnover[mask],
        "strategy_return": returns[mask],
        "market_return": data.loc[mask, "market_return"],
    }).copy()
    period["equity"] = (1 + period["strategy_return"]).cumprod()
    metrics = performance_metrics(
        period["strategy_return"],
        positions=period["position"],
        turnover=period["turnover"],
    )
    entries = period["position"].eq(-1) & period["position"].shift(1, fill_value=0).eq(0)
    metrics["entries"] = int(entries.sum())
    return period, metrics


def main() -> None:
    root = Path(__file__).resolve().parent
    data = pd.read_csv(root / "results/oos_daily.csv", parse_dates=["date"])
    lagged_news = data["news_score"].shift(1)
    technical_filter = (
        (data["close"] < data["sma"])
        & (data["rsi"] < (100 - data["rsi_threshold"]))
    )

    baseline_events = (lagged_news > 0.20) & technical_filter
    baseline_holds = pd.Series(0, index=data.index, dtype=int)
    baseline_holds.loc[baseline_events] = 1

    moderate_events = (lagged_news > 0.20) & (lagged_news <= 0.30) & technical_filter
    strong_events = (lagged_news > 0.30) & technical_filter
    hybrid_holds = pd.Series(0, index=data.index, dtype=int)
    hybrid_holds.loc[moderate_events] = 1
    hybrid_holds.loc[strong_events] = 3

    baseline, baseline_metrics = evaluate(data, baseline_holds)
    hybrid, hybrid_metrics = evaluate(data, hybrid_holds)
    benchmark_metrics = performance_metrics(baseline["market_return"])

    period_mask = data["date"].between(START, END)
    summary = {
        "period": {"start": START.date().isoformat(), "end": END.date().isoformat()},
        "rule": {
            "moderate": "0.20 < lagged sentiment <= 0.30: short 1 day",
            "strong": "lagged sentiment > 0.30: short 3 days",
            "moderate_events": int(moderate_events[period_mask].sum()),
            "strong_events": int(strong_events[period_mask].sum()),
        },
        "hybrid": hybrid_metrics,
        "baseline_0.20_one_day": baseline_metrics,
        "aapl_buy_and_hold": benchmark_metrics,
        "warning": "Development diagnostic on previously examined data; not a fresh holdout.",
    }

    output = pd.DataFrame({
        "date": baseline["date"],
        "market_return": baseline["market_return"],
        "baseline_position": baseline["position"],
        "baseline_return": baseline["strategy_return"],
        "baseline_equity": baseline["equity"],
        "hybrid_position": hybrid["position"],
        "hybrid_return": hybrid["strategy_return"],
        "hybrid_equity": hybrid["equity"],
    })
    output["benchmark_equity"] = (1 + output["market_return"]).cumprod()

    results = root / "results"
    output.to_csv(results / "quick_short_hybrid_daily.csv", index=False)
    (results / "quick_short_hybrid_summary.json").write_text(json.dumps(summary, indent=2))

    plt.figure(figsize=(10, 5.5))
    plt.plot(output["date"], output["hybrid_equity"], label="Tiered short rule", linewidth=2)
    plt.plot(output["date"], output["baseline_equity"], label="Baseline: >0.20, 1 day")
    plt.plot(output["date"], output["benchmark_equity"], label="AAPL buy & hold", alpha=0.7)
    plt.title("Tiered short rule diagnostic: Jan-Nov 2024")
    plt.ylabel("Growth of $1")
    plt.grid(alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(results / "quick_short_hybrid_equity.png", dpi=160)
    plt.close()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
