"""Causal indicators, signals, and performance metrics for the AAPL strategy."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd


TRADING_DAYS = 252


def calculate_rsi(close: pd.Series, window: int = 14) -> pd.Series:
    """Wilder-style RSI using only current and past closes."""
    delta = close.diff()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)
    avg_gain = gains.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()
    avg_loss = losses.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()
    relative_strength = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + relative_strength))
    return rsi.where(avg_loss.ne(0), 100.0)


def add_indicators(data: pd.DataFrame, sma_window: int, rsi_window: int = 14) -> pd.DataFrame:
    result = data.copy()
    result["sma"] = result["close"].rolling(sma_window, min_periods=sma_window).mean()
    result["rsi"] = calculate_rsi(result["close"], rsi_window)
    return result


def make_signals(
    data: pd.DataFrame,
    *,
    sma_window: int,
    rsi_threshold: int,
    sentiment_lower: float = -0.05,
    sentiment_upper: float = 0.20,
    sentiment_lag: int = 1,
) -> pd.DataFrame:
    """Create the repaired version of the user's technical/news signal.

    Long: prior-day news is negative, price is above SMA, RSI shows positive momentum.
    Short: prior-day news is positive, price is below SMA, RSI shows negative momentum.
    """
    result = add_indicators(data, sma_window=sma_window)
    lagged_news = result["news_score"].shift(sentiment_lag)

    long_condition = (
        (lagged_news < sentiment_lower)
        & (result["close"] > result["sma"])
        & (result["rsi"] > rsi_threshold)
    )
    short_condition = (
        (lagged_news > sentiment_upper)
        & (result["close"] < result["sma"])
        & (result["rsi"] < (100 - rsi_threshold))
    )

    result["signal"] = 0
    result.loc[long_condition, "signal"] = 1
    result.loc[short_condition, "signal"] = -1
    return result


def add_returns(data: pd.DataFrame, transaction_cost_bps: float = 5.0) -> pd.DataFrame:
    """Apply close-to-close positions with one-bar execution lag and trading costs."""
    result = data.copy()
    result["market_return"] = result["close"].pct_change().fillna(0.0)
    result["position"] = result["signal"].shift(1).fillna(0).astype(int)
    turnover = result["position"].diff().abs()
    turnover.iloc[0] = abs(result["position"].iloc[0])
    result["turnover"] = turnover
    result["transaction_cost"] = turnover * transaction_cost_bps / 10_000
    result["strategy_return_gross"] = result["position"] * result["market_return"]
    result["strategy_return"] = result["strategy_return_gross"] - result["transaction_cost"]
    return result


def performance_metrics(
    returns: pd.Series,
    *,
    positions: pd.Series | None = None,
    turnover: pd.Series | None = None,
    risk_free_rate: float = 0.04,
) -> dict[str, float | int]:
    returns = returns.fillna(0.0).astype(float)
    equity = (1 + returns).cumprod()
    total_return = float(equity.iloc[-1] - 1) if len(equity) else 0.0
    years = len(returns) / TRADING_DAYS
    cagr = float(equity.iloc[-1] ** (1 / years) - 1) if years > 0 and equity.iloc[-1] > 0 else 0.0
    volatility = float(returns.std(ddof=1) * math.sqrt(TRADING_DAYS))
    excess = returns - risk_free_rate / TRADING_DAYS
    sharpe = float(excess.mean() / returns.std(ddof=1) * math.sqrt(TRADING_DAYS)) if returns.std(ddof=1) > 0 else 0.0
    downside = returns[returns < 0].std(ddof=1)
    sortino = float(excess.mean() / downside * math.sqrt(TRADING_DAYS)) if pd.notna(downside) and downside > 0 else 0.0
    drawdown = equity / equity.cummax() - 1

    metrics: dict[str, float | int] = {
        "observations": int(len(returns)),
        "total_return": total_return,
        "cagr": cagr,
        "annualized_volatility": volatility,
        "sharpe_ratio": sharpe,
        "sortino_ratio": sortino,
        "max_drawdown": float(-drawdown.min()) if len(drawdown) else 0.0,
        "positive_day_rate": float((returns > 0).mean()) if len(returns) else 0.0,
    }
    if positions is not None:
        active = positions.ne(0)
        metrics["exposure"] = float(active.mean())
        metrics["active_days"] = int(active.sum())
        metrics["active_day_hit_rate"] = float((returns[active] > 0).mean()) if active.any() else 0.0
    if turnover is not None:
        metrics["total_turnover"] = float(turnover.sum())
        metrics["estimated_cost"] = float(turnover.sum() * 5 / 10_000)
    return metrics

