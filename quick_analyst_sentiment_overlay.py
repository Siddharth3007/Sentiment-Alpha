"""Small-window test of analyst-only earnings sentiment as a long exposure overlay."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from quick_core_overlay import build_overlay_positions
from run_backtest import DATA_END
from strategy import performance_metrics


START = pd.Timestamp("2022-01-01")
END = DATA_END
COST_PER_TURNOVER = 5 / 10_000
PARAMETERS = ((0.00, 1), (0.00, 3), (0.05, 1), (0.05, 3))


def add_analyst_long_overrides(
    baseline_positions: pd.Series,
    dates: pd.Series,
    earnings: pd.DataFrame,
    threshold: float,
    holding_days: int,
) -> tuple[pd.Series, list[dict]]:
    """Raise exposure to +1 after positive analyst tone; preserve all news shorts."""
    positions = baseline_positions.copy()
    events: list[dict] = []

    for event in earnings.itertuples(index=False):
        if event.analyst_sentiment <= threshold:
            continue

        post_call_closes = dates.index[dates > event.date]
        if len(post_call_closes) == 0:
            continue
        first_post_call_close = int(post_call_closes[0])
        # Assume an after-hours call and enter at the first subsequent close.
        # Consequently, the first return earned is the next close-to-close return.
        start = first_post_call_close + 1
        stop = min(start + holding_days, len(positions))
        if start >= len(positions):
            continue

        candidate_index = positions.index[start:stop]
        short_mask = baseline_positions.loc[candidate_index].eq(-1.0)
        positions.loc[candidate_index[~short_mask]] = 1.0
        events.append({
            "earnings_date": event.date.date().isoformat(),
            "analyst_sentiment": float(event.analyst_sentiment),
            "first_post_call_close": dates.iloc[first_post_call_close].date().isoformat(),
            "first_return_date": dates.iloc[start].date().isoformat(),
            "scheduled_holding_days": int(stop - start),
            "long_days_after_short_priority": int((~short_mask).sum()),
        })

    return positions, events


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
        period["strategy_return"], positions=period["position"], turnover=period["turnover"]
    )
    metrics["average_net_exposure"] = float(period["position"].mean())
    metrics["average_gross_exposure"] = float(period["position"].abs().mean())
    return period, metrics


def build_baseline(data: pd.DataFrame) -> pd.Series:
    lagged_news = data["news_score"].shift(1)
    long_filter = (data["close"] > data["sma"]) & (data["rsi"] > data["rsi_threshold"])
    short_filter = (
        (data["close"] < data["sma"])
        & (data["rsi"] < (100 - data["rsi_threshold"]))
    )
    long_events = (lagged_news < -0.05) & long_filter
    moderate_shorts = (lagged_news > 0.20) & (lagged_news <= 0.30) & short_filter
    strong_shorts = (lagged_news > 0.30) & short_filter
    return build_overlay_positions(long_events, moderate_shorts, strong_shorts)


def main() -> None:
    root = Path(__file__).resolve().parent
    data = pd.read_csv(root / "results/oos_daily.csv", parse_dates=["date"])
    earnings = pd.read_csv(root / "data/aapl_earnings_features.csv", parse_dates=["date"])
    earnings = earnings[earnings["date"].between(START, END)].copy()

    baseline_positions = build_baseline(data)
    baseline, baseline_metrics = evaluate(data, baseline_positions)
    benchmark_metrics = performance_metrics(baseline["market_return"])

    daily = pd.DataFrame({
        "date": baseline["date"],
        "market_return": baseline["market_return"],
        "baseline_position": baseline["position"],
        "baseline_return": baseline["strategy_return"],
        "baseline_equity": baseline["equity"],
    })
    daily["benchmark_equity"] = (1 + daily["market_return"]).cumprod()

    grid: list[dict] = []
    event_logs: dict[str, list[dict]] = {}
    for threshold, holding_days in PARAMETERS:
        label = f"threshold_{threshold:.2f}_hold_{holding_days}d"
        positions, events = add_analyst_long_overrides(
            baseline_positions, data["date"], earnings, threshold, holding_days
        )
        period, metrics = evaluate(data, positions)
        for event in events:
            event_start = pd.Timestamp(event["first_return_date"])
            matching_rows = period.index[period["date"].eq(event_start)]
            if len(matching_rows):
                start_index = period.index.get_loc(matching_rows[0])
                stop_index = start_index + event["scheduled_holding_days"]
                event_returns = period.iloc[start_index:stop_index]["strategy_return"]
                baseline_returns = baseline.iloc[start_index:stop_index]["strategy_return"]
                event["incremental_simple_return_vs_baseline"] = float(
                    (event_returns.to_numpy() - baseline_returns.to_numpy()).sum()
                )
        daily[f"{label}_position"] = period["position"]
        daily[f"{label}_return"] = period["strategy_return"]
        daily[f"{label}_equity"] = period["equity"]
        grid.append({
            "label": label,
            "analyst_threshold": threshold,
            "holding_days": holding_days,
            "qualifying_calls": len(events),
            **metrics,
        })
        event_logs[label] = events

    best = max(grid, key=lambda row: row["total_return"])
    summary = {
        "period": {"start": START.date().isoformat(), "end": END.date().isoformat()},
        "earnings_calls_available": int(len(earnings)),
        "rule": {
            "normal_position": 0.5,
            "analyst_signal": "analyst_sentiment > threshold",
            "signal_position": 1.0,
            "executive_sentiment_used": False,
            "sue_used": False,
            "news_shorts_have_priority": True,
            "execution": "Enter at first post-call close; earn returns beginning next close",
        },
        "parameter_grid": grid,
        "best_by_total_return": best["label"],
        "event_logs": event_logs,
        "core_news_baseline": baseline_metrics,
        "aapl_buy_and_hold": benchmark_metrics,
        "warning": (
            "Post-hoc development test with 12 calls; the selected parameter is not "
            "independent validation."
        ),
    }

    results = root / "results"
    daily.to_csv(results / "quick_analyst_sentiment_overlay_daily.csv", index=False)
    (results / "quick_analyst_sentiment_overlay_summary.json").write_text(
        json.dumps(summary, indent=2)
    )

    plt.figure(figsize=(10.5, 5.8))
    plt.plot(daily["date"], daily["baseline_equity"], label="Core + news baseline", linewidth=2)
    for row in grid:
        label = row["label"]
        plt.plot(
            daily["date"],
            daily[f"{label}_equity"],
            label=f"Analyst > {row['analyst_threshold']:.2f}, {row['holding_days']}d",
            alpha=0.85,
        )
    plt.plot(daily["date"], daily["benchmark_equity"], label="AAPL buy & hold", alpha=0.65)
    plt.title("Analyst-only earnings overlay diagnostic: 2022–2024")
    plt.ylabel("Growth of $1")
    plt.grid(alpha=0.25)
    plt.legend(ncol=2, fontsize=8.5)
    plt.tight_layout()
    plt.savefig(results / "quick_analyst_sentiment_overlay_equity.png", dpi=160)
    plt.close()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
