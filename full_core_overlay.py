"""Full-period evaluation of the frozen 50% core plus news-overlay rule."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from scipy import stats

from quick_core_overlay import build_overlay_positions
from quick_short_hybrid import build_positions as build_short_positions
from strategy import performance_metrics


COST_PER_TURNOVER = 5 / 10_000


def evaluate(data: pd.DataFrame, positions: pd.Series) -> tuple[pd.Series, pd.Series, dict]:
    turnover = positions.diff().abs()
    turnover.iloc[0] = abs(positions.iloc[0])
    returns = positions * data["market_return"] - turnover * COST_PER_TURNOVER
    metrics = performance_metrics(returns, positions=positions, turnover=turnover)
    metrics["average_net_exposure"] = float(positions.mean())
    metrics["average_gross_exposure"] = float(positions.abs().mean())
    return returns, turnover, metrics


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
    overlay_returns, overlay_turnover, overlay_metrics = evaluate(data, overlay_positions)
    overlay_metrics["days_at_core_0.5"] = int(overlay_positions.eq(0.5).sum())
    overlay_metrics["days_at_long_1.0"] = int(overlay_positions.eq(1.0).sum())
    overlay_metrics["days_at_short_minus_1.0"] = int(overlay_positions.eq(-1.0).sum())

    core_positions = pd.Series(0.5, index=data.index, dtype=float)
    core_returns, _, core_metrics = evaluate(data, core_positions)

    short_holds = pd.Series(0, index=data.index, dtype=int)
    short_holds.loc[moderate_short_events] = 1
    short_holds.loc[strong_short_events] = 3
    tiered_short_positions = build_short_positions(short_holds)
    tiered_short_returns, _, tiered_short_metrics = evaluate(data, tiered_short_positions)

    original_metrics = performance_metrics(
        data["strategy_return"], positions=data["position"], turnover=data["turnover"]
    )
    benchmark_metrics = performance_metrics(data["market_return"])
    excess = overlay_returns - data["market_return"]
    t_stat, p_value = stats.ttest_1samp(excess, 0.0, nan_policy="omit")

    summary = {
        "period": {
            "start": data["date"].min().date().isoformat(),
            "end": data["date"].max().date().isoformat(),
            "observations": int(len(data)),
        },
        "frozen_rule": {
            "normal_position": 0.5,
            "negative_news_recovery_position": 1.0,
            "negative_news_recovery_holding_days": 1,
            "moderate_short_range": "0.20 < lagged sentiment <= 0.30",
            "moderate_short_holding_days": 1,
            "strong_short_range": "lagged sentiment > 0.30",
            "strong_short_holding_days": 3,
            "short_position": -1.0,
            "short_priority": True,
            "transaction_cost_bps_per_unit_turnover": 5.0,
        },
        "events": {
            "negative_news_recovery": int(long_events.sum()),
            "moderate_short": int(moderate_short_events.sum()),
            "strong_short": int(strong_short_events.sum()),
        },
        "core_plus_overlay": overlay_metrics,
        "passive_50_percent_aapl": core_metrics,
        "tiered_short_only": tiered_short_metrics,
        "original_long_short": original_metrics,
        "aapl_buy_and_hold": benchmark_metrics,
        "paired_daily_excess_return_test_vs_aapl": {
            "t_statistic": float(t_stat),
            "p_value_two_sided": float(p_value),
        },
        "warning": "Historical development-period evaluation; the remaining cash earns 0%.",
    }

    output = data[["date", "market_return"]].copy()
    output["overlay_position"] = overlay_positions
    output["overlay_turnover"] = overlay_turnover
    output["overlay_return"] = overlay_returns
    output["overlay_equity"] = (1 + overlay_returns).cumprod()
    output["passive_50_return"] = core_returns
    output["passive_50_equity"] = (1 + core_returns).cumprod()
    output["tiered_short_return"] = tiered_short_returns
    output["tiered_short_equity"] = (1 + tiered_short_returns).cumprod()
    output["original_strategy_return"] = data["strategy_return"]
    output["original_strategy_equity"] = (1 + data["strategy_return"]).cumprod()
    output["benchmark_equity"] = (1 + data["market_return"]).cumprod()

    results = root / "results"
    output.to_csv(results / "full_core_overlay_daily.csv", index=False)
    (results / "full_core_overlay_summary.json").write_text(json.dumps(summary, indent=2))

    plt.figure(figsize=(11, 6))
    plt.plot(output["date"], output["overlay_equity"], label="50% core + news overlay", linewidth=2)
    plt.plot(output["date"], output["original_strategy_equity"], label="Original long + short")
    plt.plot(output["date"], output["passive_50_equity"], label="Passive 50% AAPL")
    plt.plot(output["date"], output["benchmark_equity"], label="AAPL buy & hold", alpha=0.75)
    plt.title("Full deduplicated walk-forward period: core-plus-news overlay")
    plt.ylabel("Growth of $1")
    plt.grid(alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(results / "full_core_overlay_equity.png", dpi=160)
    plt.close()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

