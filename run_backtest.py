"""Run rolling calibration and deduplicated out-of-sample evaluation."""

from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

from strategy import add_returns, make_signals, performance_metrics


TRAIN_WINDOW = 132
TEST_WINDOW = 56
STEP = 50
SMA_WINDOWS = (10, 20, 30)
RSI_THRESHOLDS = (40, 45, 50, 55, 60)
TRANSACTION_COST_BPS = 5.0


def load_data(path: Path) -> pd.DataFrame:
    data = pd.read_csv(path, parse_dates=["date"])
    expected = {"date", "close", "news_score"}
    missing = expected.difference(data.columns)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")
    data = data.loc[:, ["date", "close", "news_score"]].copy()
    data = data.drop_duplicates("date").sort_values("date").reset_index(drop=True)
    data["close"] = pd.to_numeric(data["close"], errors="raise")
    data["news_score"] = pd.to_numeric(data["news_score"], errors="coerce").fillna(0.0)
    return data


def evaluate_slice(enriched: pd.DataFrame, start: int, end: int) -> tuple[pd.DataFrame, dict]:
    section = enriched.iloc[max(0, start - 1):end].copy()
    section = add_returns(section, transaction_cost_bps=TRANSACTION_COST_BPS)
    section = section.iloc[1:].copy() if start > 0 else section.copy()
    metrics = performance_metrics(
        section["strategy_return"], positions=section["position"], turnover=section["turnover"]
    )
    return section, metrics


def calibrate(data: pd.DataFrame, train_start: int, train_end: int) -> tuple[dict, list[dict]]:
    candidates = []
    for sma_window, rsi_threshold in itertools.product(SMA_WINDOWS, RSI_THRESHOLDS):
        enriched = make_signals(
            data,
            sma_window=sma_window,
            rsi_threshold=rsi_threshold,
        )
        _, metrics = evaluate_slice(enriched, train_start, train_end)
        candidates.append({
            "sma_window": sma_window,
            "rsi_threshold": rsi_threshold,
            **metrics,
        })
    best = max(candidates, key=lambda row: (row["sharpe_ratio"], row["total_return"]))
    return best, candidates


def run_walk_forward(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    window_rows = []
    calibration_rows = []
    oos_parts = []
    start = 0
    window_id = 0

    while start + TRAIN_WINDOW + TEST_WINDOW <= len(data):
        window_id += 1
        train_start = start
        train_end = start + TRAIN_WINDOW
        test_start = train_end
        test_end = test_start + TEST_WINDOW

        best, candidates = calibrate(data, train_start, train_end)
        for candidate in candidates:
            calibration_rows.append({"window": window_id, **candidate})

        enriched = make_signals(
            data,
            sma_window=int(best["sma_window"]),
            rsi_threshold=int(best["rsi_threshold"]),
        )
        test, strategy_metrics = evaluate_slice(enriched, test_start, test_end)
        benchmark_metrics = performance_metrics(test["market_return"])
        test["window"] = window_id
        test["sma_window"] = int(best["sma_window"])
        test["rsi_threshold"] = int(best["rsi_threshold"])
        oos_parts.append(test)

        window_rows.append({
            "window": window_id,
            "train_start": data.iloc[train_start]["date"],
            "train_end": data.iloc[train_end - 1]["date"],
            "test_start": data.iloc[test_start]["date"],
            "test_end": data.iloc[test_end - 1]["date"],
            "sma_window": int(best["sma_window"]),
            "rsi_threshold": int(best["rsi_threshold"]),
            "train_sharpe": best["sharpe_ratio"],
            "strategy_return": strategy_metrics["total_return"],
            "strategy_sharpe": strategy_metrics["sharpe_ratio"],
            "strategy_max_drawdown": strategy_metrics["max_drawdown"],
            "strategy_exposure": strategy_metrics["exposure"],
            "benchmark_return": benchmark_metrics["total_return"],
            "benchmark_sharpe": benchmark_metrics["sharpe_ratio"],
            "benchmark_max_drawdown": benchmark_metrics["max_drawdown"],
        })
        start += STEP

    windows = pd.DataFrame(window_rows)
    calibration = pd.DataFrame(calibration_rows)
    all_oos = pd.concat(oos_parts, ignore_index=True)
    # Test windows overlap by six days. Keep the earliest genuine OOS prediction for each date.
    stitched = all_oos.sort_values(["date", "window"]).drop_duplicates("date", keep="first")
    stitched = stitched.sort_values("date").reset_index(drop=True)
    # Recompute costs after stitching so parameter changes at window boundaries
    # are charged against the position actually retained on the preceding date.
    stitched["turnover"] = stitched["position"].diff().abs()
    stitched.loc[0, "turnover"] = abs(stitched.loc[0, "position"])
    stitched["transaction_cost"] = stitched["turnover"] * TRANSACTION_COST_BPS / 10_000
    stitched["strategy_return"] = stitched["strategy_return_gross"] - stitched["transaction_cost"]
    stitched["strategy_equity"] = (1 + stitched["strategy_return"]).cumprod()
    stitched["benchmark_equity"] = (1 + stitched["market_return"]).cumprod()
    return windows, calibration, stitched


def build_summary(windows: pd.DataFrame, stitched: pd.DataFrame) -> dict:
    strategy = performance_metrics(
        stitched["strategy_return"], positions=stitched["position"], turnover=stitched["turnover"]
    )
    strategy_gross = performance_metrics(
        stitched["strategy_return_gross"], positions=stitched["position"]
    )
    benchmark = performance_metrics(stitched["market_return"])
    excess = stitched["strategy_return"] - stitched["market_return"]
    t_stat, p_value = stats.ttest_1samp(excess, 0.0, nan_policy="omit")
    return {
        "method": {
            "train_window": TRAIN_WINDOW,
            "test_window": TEST_WINDOW,
            "step": STEP,
            "overlap_policy": "Earliest prediction retained for overlapping test dates",
            "transaction_cost_bps_per_unit_turnover": TRANSACTION_COST_BPS,
            "sentiment_lag_days": 1,
            "sentiment_lower": -0.05,
            "sentiment_upper": 0.20,
            "sma_grid": list(SMA_WINDOWS),
            "rsi_threshold_grid": list(RSI_THRESHOLDS),
        },
        "period": {
            "start": stitched["date"].min().date().isoformat(),
            "end": stitched["date"].max().date().isoformat(),
            "unique_oos_days": int(len(stitched)),
            "walk_forward_windows": int(len(windows)),
        },
        "strategy": strategy,
        "strategy_before_costs": strategy_gross,
        "benchmark": benchmark,
        "consistency": {
            "positive_windows": int((windows["strategy_return"] > 0).sum()),
            "windows_beating_benchmark": int((windows["strategy_return"] > windows["benchmark_return"]).sum()),
            "mean_window_strategy_return": float(windows["strategy_return"].mean()),
            "mean_window_benchmark_return": float(windows["benchmark_return"].mean()),
        },
        "paired_daily_excess_return_test": {
            "t_statistic": float(t_stat),
            "p_value_two_sided": float(p_value),
        },
    }


def save_plot(stitched: pd.DataFrame, path: Path) -> None:
    plt.figure(figsize=(11, 6))
    plt.plot(stitched["date"], stitched["strategy_equity"], label="News + technical strategy", linewidth=2)
    plt.plot(stitched["date"], stitched["benchmark_equity"], label="AAPL buy & hold", linewidth=1.5)
    plt.title("Deduplicated walk-forward out-of-sample equity")
    plt.xlabel("Date")
    plt.ylabel("Growth of $1")
    plt.grid(alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(path, dpi=160)
    plt.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=Path("data/aapl_news_scores.csv"))
    parser.add_argument("--output", type=Path, default=Path("results"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    data = load_data(args.data)
    windows, calibration, stitched = run_walk_forward(data)
    summary = build_summary(windows, stitched)

    windows.to_csv(args.output / "window_results.csv", index=False)
    calibration.to_csv(args.output / "calibration_grid.csv", index=False)
    stitched.to_csv(args.output / "oos_daily.csv", index=False)
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2))
    save_plot(stitched, args.output / "equity_curve.png")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
