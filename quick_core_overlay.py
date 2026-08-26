"""Test a 50% AAPL core with news-driven long and tiered-short overlays."""

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


def next_day_mask(events: pd.Series) -> pd.Series:
    return events.shift(1, fill_value=False).astype(bool)


def build_overlay_positions(
    long_events: pd.Series,
    moderate_short_events: pd.Series,
    strong_short_events: pd.Series,
) -> pd.Series:
    positions = pd.Series(0.5, index=long_events.index, dtype=float)

    # Long recovery lasts for the following close-to-close return.
    positions.loc[next_day_mask(long_events)] = 1.0

    # Short events override core and recovery-long positions.
    positions.loc[next_day_mask(moderate_short_events)] = -1.0
    for event_index in strong_short_events[strong_short_events].index:
        start = event_index + 1
        stop = min(start + 3, len(positions))
        if start < len(positions):
            positions.iloc[start:stop] = -1.0
    return positions


def evaluate(data: pd.DataFrame, positions: pd.Series) -> tuple[pd.DataFrame, dict]:
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
    metrics["average_net_exposure"] = float(period["position"].mean())
    metrics["average_gross_exposure"] = float(period["position"].abs().mean())
    metrics["days_at_core_0.5"] = int(period["position"].eq(0.5).sum())
    metrics["days_at_long_1.0"] = int(period["position"].eq(1.0).sum())
    metrics["days_at_short_minus_1.0"] = int(period["position"].eq(-1.0).sum())
    return period, metrics


def main() -> None:
    root = Path(__file__).resolve().parent
    data = pd.read_csv(root / "results/oos_daily.csv", parse_dates=["date"])
    lagged_news = data["news_score"].shift(1)

    long_filter = (
        (data["close"] > data["sma"])
        & (data["rsi"] > data["rsi_threshold"])
    )
    short_filter = (
        (data["close"] < data["sma"])
        & (data["rsi"] < (100 - data["rsi_threshold"]))
    )
    long_events = (lagged_news < -0.05) & long_filter
    moderate_short_events = (lagged_news > 0.20) & (lagged_news <= 0.30) & short_filter
    strong_short_events = (lagged_news > 0.30) & short_filter

    overlay_positions = build_overlay_positions(
        long_events, moderate_short_events, strong_short_events
    )
    overlay, overlay_metrics = evaluate(data, overlay_positions)

    core_positions = pd.Series(0.5, index=data.index, dtype=float)
    core, core_metrics = evaluate(data, core_positions)
    benchmark_metrics = performance_metrics(overlay["market_return"])

    mask = data["date"].between(START, END)
    summary = {
        "period": {"start": START.date().isoformat(), "end": END.date().isoformat()},
        "position_rules": {
            "normal": 0.5,
            "negative_news_recovery": 1.0,
            "moderate_short": -1.0,
            "strong_short": -1.0,
            "short_priority": True,
            "long_holding_days": 1,
            "moderate_short_holding_days": 1,
            "strong_short_holding_days": 3,
        },
        "events": {
            "negative_news_recovery": int(long_events[mask].sum()),
            "moderate_short": int(moderate_short_events[mask].sum()),
            "strong_short": int(strong_short_events[mask].sum()),
        },
        "core_plus_overlay": overlay_metrics,
        "passive_50_percent_aapl": core_metrics,
        "aapl_buy_and_hold": benchmark_metrics,
        "warning": "Development diagnostic on previously examined data; remaining 50% cash earns 0%.",
    }

    output = pd.DataFrame({
        "date": overlay["date"],
        "market_return": overlay["market_return"],
        "overlay_position": overlay["position"],
        "overlay_turnover": overlay["turnover"],
        "overlay_return": overlay["strategy_return"],
        "overlay_equity": overlay["equity"],
        "core_return": core["strategy_return"],
        "core_equity": core["equity"],
    })
    output["benchmark_equity"] = (1 + output["market_return"]).cumprod()

    results = root / "results"
    output.to_csv(results / "quick_core_overlay_daily.csv", index=False)
    (results / "quick_core_overlay_summary.json").write_text(json.dumps(summary, indent=2))

    plt.figure(figsize=(10, 5.5))
    plt.plot(output["date"], output["overlay_equity"], label="50% core + news overlay", linewidth=2)
    plt.plot(output["date"], output["core_equity"], label="Passive 50% AAPL")
    plt.plot(output["date"], output["benchmark_equity"], label="AAPL buy & hold", alpha=0.75)
    plt.title("Core-plus-news overlay diagnostic: Jan–Nov 2024")
    plt.ylabel("Growth of $1")
    plt.grid(alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(results / "quick_core_overlay_equity.png", dpi=160)
    plt.close()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
