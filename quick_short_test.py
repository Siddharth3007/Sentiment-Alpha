"""Quick short-only holding-period diagnostic using saved OOS signals."""

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


def short_positions(events: pd.Series, holding_days: int) -> pd.Series:
    """Enter on the close after a short event and hold for a fixed number of returns."""
    positions = pd.Series(0, index=events.index, dtype=int)
    event_locations = events[events].index
    for event_index in event_locations:
        start = event_index + 1
        stop = min(start + holding_days, len(positions))
        if start < len(positions):
            positions.iloc[start:stop] = -1
    return positions


def evaluate(data: pd.DataFrame, holding_days: int) -> tuple[pd.DataFrame, dict]:
    result = data.copy()
    result["position"] = short_positions(result["signal"].eq(-1), holding_days)
    result["turnover"] = result["position"].diff().abs()
    result.loc[0, "turnover"] = abs(result.loc[0, "position"])
    result["strategy_return"] = (
        result["position"] * result["market_return"]
        - result["turnover"] * COST_PER_TURNOVER
    )
    period = result[result["date"].between(START, END)].copy()
    metrics = performance_metrics(
        period["strategy_return"], positions=period["position"], turnover=period["turnover"]
    )
    entries = period["position"].eq(-1) & period["position"].shift(1, fill_value=0).eq(0)
    metrics["entries"] = int(entries.sum())
    period["equity"] = (1 + period["strategy_return"]).cumprod()
    return period, metrics


def main() -> None:
    root = Path(__file__).resolve().parent
    data = pd.read_csv(root / "results/oos_daily.csv", parse_dates=["date"])

    one_day, one_metrics = evaluate(data, 1)
    three_day, three_metrics = evaluate(data, 3)
    benchmark_metrics = performance_metrics(one_day["market_return"])

    output = pd.DataFrame({
        "date": one_day["date"],
        "market_return": one_day["market_return"],
        "short_signal": one_day["signal"].eq(-1).astype(int),
        "one_day_position": one_day["position"],
        "one_day_return": one_day["strategy_return"],
        "one_day_equity": one_day["equity"],
        "three_day_position": three_day["position"],
        "three_day_return": three_day["strategy_return"],
        "three_day_equity": three_day["equity"],
    })
    output["benchmark_equity"] = (1 + output["market_return"]).cumprod()

    summary = {
        "period": {"start": START.date().isoformat(), "end": END.date().isoformat()},
        "one_day_short": one_metrics,
        "three_day_short": three_metrics,
        "aapl_buy_and_hold": benchmark_metrics,
        "warning": "Diagnostic on previously examined OOS data; not a fresh untouched holdout.",
    }

    results = root / "results"
    output.to_csv(results / "quick_short_2024_daily.csv", index=False)
    (results / "quick_short_2024_summary.json").write_text(json.dumps(summary, indent=2))

    plt.figure(figsize=(10, 5.5))
    plt.plot(output["date"], output["one_day_equity"], label="Short only - 1 day")
    plt.plot(output["date"], output["three_day_equity"], label="Short only - 3 days")
    plt.plot(output["date"], output["benchmark_equity"], label="AAPL buy & hold", alpha=0.75)
    plt.title("Quick short-only diagnostic: Jan-Nov 2024")
    plt.ylabel("Growth of $1")
    plt.grid(alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(results / "quick_short_2024_equity.png", dpi=160)
    plt.close()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
