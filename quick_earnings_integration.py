"""Small-window integration of earnings-call features with the news overlay."""

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
EARNINGS_HOLDING_DAYS = 3


def add_earnings_overrides(
    positions: pd.Series,
    dates: pd.Series,
    earnings: pd.DataFrame,
) -> tuple[pd.Series, list[dict]]:
    result = positions.copy()
    event_log: list[dict] = []

    for event in earnings.itertuples(index=False):
        bullish = event.sue > 0 and event.qa_sentiment > 0 and event.executive_sentiment > 0
        bearish = event.sue < 0 and event.qa_sentiment < 0 and event.executive_sentiment < 0
        if not bullish and not bearish:
            continue

        post_call_closes = dates.index[dates > event.date]
        if len(post_call_closes) == 0:
            continue
        first_post_call_close = int(post_call_closes[0])
        start = first_post_call_close + 1
        stop = min(start + EARNINGS_HOLDING_DAYS, len(result))
        if start >= len(result):
            continue

        position = 1.0 if bullish else -1.0
        result.iloc[start:stop] = position
        event_log.append({
            "earnings_date": event.date.date().isoformat(),
            "direction": "bullish" if bullish else "bearish",
            "position": position,
            "first_post_call_close": dates.iloc[first_post_call_close].date().isoformat(),
            "first_return_date": dates.iloc[start].date().isoformat(),
            "holding_days": int(stop - start),
            "sue": float(event.sue),
            "qa_sentiment": float(event.qa_sentiment),
            "executive_sentiment": float(event.executive_sentiment),
        })
    return result, event_log


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


def main() -> None:
    root = Path(__file__).resolve().parent
    data = pd.read_csv(root / "results/oos_daily.csv", parse_dates=["date"])
    earnings = pd.read_csv(root / "data/aapl_earnings_features.csv", parse_dates=["date"])
    earnings = earnings[earnings["date"].between(START, END)].copy()

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

    baseline_positions = build_overlay_positions(
        long_events, moderate_short_events, strong_short_events
    )
    earnings_positions, event_log = add_earnings_overrides(
        baseline_positions, data["date"], earnings
    )

    baseline, baseline_metrics = evaluate(data, baseline_positions)
    integrated, integrated_metrics = evaluate(data, earnings_positions)
    benchmark_metrics = performance_metrics(baseline["market_return"])

    summary = {
        "period": {"start": START.date().isoformat(), "end": END.date().isoformat()},
        "earnings_calls_available": int(len(earnings)),
        "earnings_rule": {
            "bullish": "SUE > 0 and Q&A sentiment > 0 and executive sentiment > 0",
            "bearish": "SUE < 0 and Q&A sentiment < 0 and executive sentiment < 0",
            "position": "+1 bullish / -1 bearish",
            "holding_days": EARNINGS_HOLDING_DAYS,
            "execution": "Enter at first post-call close; earn returns beginning next close",
            "priority": "Earnings override news/core positions",
        },
        "qualifying_events": event_log,
        "core_news_plus_earnings": integrated_metrics,
        "core_news_without_earnings": baseline_metrics,
        "aapl_buy_and_hold": benchmark_metrics,
        "warning": "Small historical development test with only 12 calls; not independent validation.",
    }

    output = pd.DataFrame({
        "date": baseline["date"],
        "market_return": baseline["market_return"],
        "baseline_position": baseline["position"],
        "baseline_return": baseline["strategy_return"],
        "baseline_equity": baseline["equity"],
        "earnings_position": integrated["position"],
        "earnings_return": integrated["strategy_return"],
        "earnings_equity": integrated["equity"],
    })
    output["benchmark_equity"] = (1 + output["market_return"]).cumprod()

    results = root / "results"
    output.to_csv(results / "quick_earnings_integration_daily.csv", index=False)
    (results / "quick_earnings_integration_summary.json").write_text(json.dumps(summary, indent=2))

    plt.figure(figsize=(10.5, 5.8))
    plt.plot(output["date"], output["earnings_equity"], label="Core + news + earnings", linewidth=2)
    plt.plot(output["date"], output["baseline_equity"], label="Core + news")
    plt.plot(output["date"], output["benchmark_equity"], label="AAPL buy & hold", alpha=0.75)
    plt.title("Small earnings-integration diagnostic: 2022-2024")
    plt.ylabel("Growth of $1")
    plt.grid(alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(results / "quick_earnings_integration_equity.png", dpi=160)
    plt.close()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
