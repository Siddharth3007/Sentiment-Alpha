"""Small diagnostic grid for short-news thresholds and holding periods."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from run_backtest import DATA_END
from strategy import performance_metrics


START = pd.Timestamp("2024-01-01")
END = DATA_END
HOLDING_PERIODS = (1, 2, 3, 5)
SENTIMENT_THRESHOLDS = (0.10, 0.20, 0.30)
COST_PER_TURNOVER = 5 / 10_000


def make_positions(events: pd.Series, holding_days: int) -> pd.Series:
    positions = pd.Series(0, index=events.index, dtype=int)
    for event_index in events[events].index:
        start = event_index + 1
        stop = min(start + holding_days, len(positions))
        if start < len(positions):
            positions.iloc[start:stop] = -1
    return positions


def evaluate(data: pd.DataFrame, threshold: float, holding_days: int) -> dict:
    lagged_news = data["news_score"].shift(1)
    events = (
        (lagged_news > threshold)
        & (data["close"] < data["sma"])
        & (data["rsi"] < (100 - data["rsi_threshold"]))
    )
    positions = make_positions(events, holding_days)
    turnover = positions.diff().abs()
    turnover.iloc[0] = abs(positions.iloc[0])
    returns = positions * data["market_return"] - turnover * COST_PER_TURNOVER

    mask = data["date"].between(START, END)
    period_returns = returns[mask]
    period_positions = positions[mask]
    period_turnover = turnover[mask]
    period_events = events[mask]
    metrics = performance_metrics(
        period_returns,
        positions=period_positions,
        turnover=period_turnover,
    )
    entries = period_positions.eq(-1) & period_positions.shift(1, fill_value=0).eq(0)
    return {
        "sentiment_threshold": threshold,
        "holding_days": holding_days,
        "signal_events": int(period_events.sum()),
        "entries": int(entries.sum()),
        **metrics,
    }


def save_heatmap(grid: pd.DataFrame, path: Path) -> None:
    pivot = grid.pivot(index="sentiment_threshold", columns="holding_days", values="total_return")
    values = pivot.to_numpy() * 100
    fig, ax = plt.subplots(figsize=(8, 4.8))
    image = ax.imshow(values, cmap="RdYlGn", aspect="auto")
    ax.set_xticks(range(len(pivot.columns)), labels=[str(x) for x in pivot.columns])
    ax.set_yticks(range(len(pivot.index)), labels=[f"{x:.2f}" for x in pivot.index])
    ax.set_xlabel("Holding period (trading days)")
    ax.set_ylabel("Positive-news threshold")
    ax.set_title("Short-only net return, Jan-Nov 2024")
    for row in range(values.shape[0]):
        for col in range(values.shape[1]):
            ax.text(col, row, f"{values[row, col]:.1f}%", ha="center", va="center")
    fig.colorbar(image, ax=ax, label="Net return (%)")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def main() -> None:
    root = Path(__file__).resolve().parent
    data = pd.read_csv(root / "results/oos_daily.csv", parse_dates=["date"])
    rows = [
        evaluate(data, threshold, holding_days)
        for threshold in SENTIMENT_THRESHOLDS
        for holding_days in HOLDING_PERIODS
    ]
    grid = pd.DataFrame(rows).sort_values(["sentiment_threshold", "holding_days"])
    ranked = grid.sort_values(["total_return", "sharpe_ratio"], ascending=False).reset_index(drop=True)

    results = root / "results"
    grid.to_csv(results / "quick_short_parameter_grid.csv", index=False)
    summary = {
        "period": {"start": START.date().isoformat(), "end": END.date().isoformat()},
        "combinations_tested": int(len(grid)),
        "best_by_net_return": ranked.iloc[0].to_dict(),
        "baseline_threshold_0.20_holding_1": grid[
            grid["sentiment_threshold"].eq(0.20) & grid["holding_days"].eq(1)
        ].iloc[0].to_dict(),
        "warning": "Small development grid on previously examined data; ranking is not a fresh holdout result.",
    }
    (results / "quick_short_parameter_grid_summary.json").write_text(
        json.dumps(summary, indent=2)
    )
    save_heatmap(grid, results / "quick_short_parameter_grid.png")
    print(ranked[[
        "sentiment_threshold", "holding_days", "total_return", "sharpe_ratio",
        "max_drawdown", "exposure", "entries", "signal_events"
    ]].to_string(index=False))
    print("\n" + json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
