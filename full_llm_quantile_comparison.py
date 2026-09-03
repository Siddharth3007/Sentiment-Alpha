"""Matched-period walk-forward comparison of Qwen and FinBERT news scores.

Qwen labels anonymized headlines without retrieval. Each model receives its own
training-only nonzero-news quantile thresholds, while dates, technical filters,
position rules, analyst overlay, and transaction costs remain identical.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
from scipy import stats
from transformers import AutoModelForCausalLM, AutoTokenizer

from full_core_overlay import evaluate
from full_quantile_news_overlay import (
    ANALYST_HOLDING_DAYS,
    ANALYST_THRESHOLD,
    attach_training_thresholds,
    build_quantile_positions,
    metric_with_position_counts,
)
from quick_analyst_sentiment_overlay import add_analyst_long_overrides
from quick_llm_news_test import (
    DEFAULT_SOURCE,
    LABELS,
    MODEL_ID,
    build_prompts,
    daily_scores,
    load_headlines,
)
from run_backtest import DATA_END, load_data
from strategy import performance_metrics


END = DATA_END
LABEL_VALUE = {"Positive": 1.0, "Negative": -1.0, "Neutral": 0.0}
DEFAULT_BATCH_SIZE = 12
DEFAULT_CHECKPOINT_EVERY = 1_000
MIN_VALIDATION_AGREEMENT = 0.98


def prepare_model(model_id: str) -> tuple[AutoTokenizer, AutoModelForCausalLM, str]:
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    tokenizer = AutoTokenizer.from_pretrained(model_id, local_files_only=True)
    tokenizer.padding_side = "left"
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token_id = tokenizer.eos_token_id
    dtype = torch.float16 if device == "mps" else torch.float32
    model = AutoModelForCausalLM.from_pretrained(
        model_id, torch_dtype=dtype, local_files_only=True
    )
    model.to(device)
    model.eval()
    return tokenizer, model, device


def candidate_token_ids(tokenizer: AutoTokenizer) -> list[int]:
    ids: list[int] = []
    for label in LABELS:
        encoded = tokenizer.encode(label, add_special_tokens=False)
        if len(encoded) != 1:
            raise ValueError(f"{label!r} is not a single token: {encoded}")
        ids.append(encoded[0])
    return ids


def classify_constrained(
    headlines: list[str],
    tokenizer: AutoTokenizer,
    model: AutoModelForCausalLM,
    device: str,
    batch_size: int,
    *,
    progress_prefix: str = "Classified",
) -> list[str]:
    """Choose the highest-logit allowed label at the first response token."""
    label_ids = candidate_token_ids(tokenizer)
    labels: list[str] = []
    started = time.monotonic()
    for start in range(0, len(headlines), batch_size):
        batch_headlines = headlines[start : start + batch_size]
        prompts = build_prompts(tokenizer, batch_headlines)
        encoded = tokenizer(
            prompts,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=256,
        ).to(device)
        with torch.inference_mode():
            logits = model(**encoded, logits_to_keep=1).logits[:, -1, label_ids]
        choices = logits.argmax(dim=1).detach().cpu().tolist()
        labels.extend(LABELS[choice] for choice in choices)
        completed = min(start + batch_size, len(headlines))
        if completed == len(headlines) or completed % (batch_size * 20) == 0:
            elapsed = max(time.monotonic() - started, 1e-6)
            rate = completed / elapsed
            eta_minutes = (len(headlines) - completed) / rate / 60
            print(
                f"{progress_prefix} {completed}/{len(headlines)} "
                f"({rate:.1f}/s, ETA {eta_minutes:.1f} min)",
                flush=True,
            )
    return labels


def validate_constrained_labels(
    root: Path,
    all_headlines: pd.DataFrame,
    tokenizer: AutoTokenizer,
    model: AutoModelForCausalLM,
    device: str,
    batch_size: int,
) -> dict:
    pilot_path = root / "results/quick_llm_news_labels.csv"
    if not pilot_path.exists():
        raise FileNotFoundError("Saved generated-label pilot is required for validation")
    pilot = pd.read_csv(pilot_path, usecols=["headline_hash", "label"])
    pilot = pilot.drop_duplicates("headline_hash")
    matched = pilot.merge(
        all_headlines[["headline_hash", "headline"]].drop_duplicates("headline_hash"),
        on="headline_hash",
        how="inner",
        validate="one_to_one",
    )
    if len(matched) < 100:
        raise ValueError(f"Only {len(matched)} saved pilot labels could be reconstructed")
    predicted = classify_constrained(
        matched["headline"].tolist(),
        tokenizer,
        model,
        device,
        batch_size,
        progress_prefix="Validated",
    )
    matched["constrained_label"] = predicted
    agreement = float(matched["label"].eq(matched["constrained_label"]).mean())
    result = {
        "observations": int(len(matched)),
        "agreement_with_generated_labels": agreement,
        "minimum_required_agreement": MIN_VALIDATION_AGREEMENT,
        "generated_label_counts": {
            str(key): int(value)
            for key, value in matched["label"].value_counts().items()
        },
        "constrained_label_counts": {
            str(key): int(value)
            for key, value in matched["constrained_label"].value_counts().items()
        },
    }
    if agreement < MIN_VALIDATION_AGREEMENT:
        raise RuntimeError(
            f"Constrained-label agreement {agreement:.2%} is below "
            f"{MIN_VALIDATION_AGREEMENT:.0%}; refusing the full run"
        )
    return result


def load_label_cache(root: Path) -> pd.DataFrame:
    cache_path = root / "results/full_llm_qwen3_0_6b_label_cache.csv"
    parts: list[pd.DataFrame] = []
    if cache_path.exists():
        parts.append(pd.read_csv(cache_path, dtype=str))
    pilot_path = root / "results/quick_llm_news_labels.csv"
    if pilot_path.exists():
        parts.append(pd.read_csv(pilot_path, usecols=["headline_hash", "label"], dtype=str))
    if not parts:
        return pd.DataFrame(columns=["headline_hash", "label"])
    cache = pd.concat(parts, ignore_index=True)
    cache = cache[cache["label"].isin(LABELS)].drop_duplicates("headline_hash", keep="first")
    return cache[["headline_hash", "label"]]


def save_label_cache(root: Path, cache: pd.DataFrame) -> None:
    path = root / "results/full_llm_qwen3_0_6b_label_cache.csv"
    cache[["headline_hash", "label"]].drop_duplicates("headline_hash").to_csv(
        path, index=False
    )


def classify_with_checkpoints(
    root: Path,
    unique_headlines: pd.DataFrame,
    tokenizer: AutoTokenizer,
    model: AutoModelForCausalLM,
    device: str,
    batch_size: int,
    checkpoint_every: int,
) -> pd.DataFrame:
    cache = load_label_cache(root)
    missing = unique_headlines[
        ~unique_headlines["headline_hash"].isin(set(cache["headline_hash"]))
    ].copy()
    missing = (
        missing.assign(_prompt_length=missing["headline"].str.len())
        .sort_values(["_prompt_length", "headline_hash"])
        .drop(columns="_prompt_length")
        .reset_index(drop=True)
    )
    print(
        f"Label cache: {len(cache)} present; {len(missing)} unique headlines remaining",
        flush=True,
    )
    for start in range(0, len(missing), checkpoint_every):
        chunk = missing.iloc[start : start + checkpoint_every].copy()
        chunk["label"] = classify_constrained(
            chunk["headline"].tolist(),
            tokenizer,
            model,
            device,
            batch_size,
            progress_prefix=f"Checkpoint {start // checkpoint_every + 1}",
        )
        cache = pd.concat(
            [cache, chunk[["headline_hash", "label"]]], ignore_index=True
        ).drop_duplicates("headline_hash", keep="first")
        save_label_cache(root, cache)
        print(f"Saved {len(cache)} cached labels", flush=True)
    return unique_headlines.merge(
        cache, on="headline_hash", how="left", validate="one_to_one"
    )


def hac_mean_test(values: pd.Series, max_lags: int | None = None) -> dict[str, float | int]:
    """Two-sided Newey-West test that the paired daily mean equals zero."""
    x = pd.to_numeric(values, errors="coerce").dropna().to_numpy(dtype=float)
    n = len(x)
    if n < 3:
        return {"observations": n, "t_statistic": math.nan, "p_value_two_sided": math.nan}
    lags = max_lags if max_lags is not None else int(math.floor(4 * (n / 100) ** (2 / 9)))
    centered = x - x.mean()
    long_run_variance = float(np.dot(centered, centered) / n)
    for lag in range(1, min(lags, n - 1) + 1):
        weight = 1 - lag / (lags + 1)
        covariance = float(np.dot(centered[lag:], centered[:-lag]) / n)
        long_run_variance += 2 * weight * covariance
    standard_error = math.sqrt(max(long_run_variance, 0.0) / n)
    t_statistic = float(x.mean() / standard_error) if standard_error > 0 else math.nan
    p_value = float(2 * stats.t.sf(abs(t_statistic), df=n - 1)) if math.isfinite(t_statistic) else math.nan
    return {
        "observations": n,
        "max_lags": int(lags),
        "mean_daily_difference": float(x.mean()),
        "annualized_mean_difference": float(x.mean() * 252),
        "t_statistic": t_statistic,
        "p_value_two_sided": p_value,
    }


def evaluate_model(
    data: pd.DataFrame, earnings: pd.DataFrame
) -> tuple[pd.DataFrame, dict, pd.DataFrame]:
    positions, events = build_quantile_positions(data)
    returns, turnover, metrics = evaluate(data, positions)
    metrics = metric_with_position_counts(metrics, positions)
    analyst_positions, analyst_events = add_analyst_long_overrides(
        positions,
        data["date"],
        earnings,
        threshold=ANALYST_THRESHOLD,
        holding_days=ANALYST_HOLDING_DAYS,
    )
    analyst_returns, analyst_turnover, analyst_metrics = evaluate(data, analyst_positions)
    analyst_metrics = metric_with_position_counts(analyst_metrics, analyst_positions)
    daily = pd.DataFrame(
        {
            "date": data["date"],
            "news_score": data["news_score"],
            "position": positions,
            "turnover": turnover,
            "return": returns,
            "analyst_position": analyst_positions,
            "analyst_turnover": analyst_turnover,
            "analyst_return": analyst_returns,
        }
    )
    summary = {
        "events": {key: int(value.sum()) for key, value in events.items()},
        "core_news": metrics,
        "core_news_plus_analyst": analyst_metrics,
        "analyst_qualifying_calls": int(len(analyst_events)),
    }
    return daily, summary, data


def threshold_distribution(thresholds: pd.DataFrame) -> dict:
    result = {}
    for column in (
        "nonzero_news_days",
        "bad_threshold",
        "moderate_threshold",
        "strong_threshold",
    ):
        result[column] = {
            "min": float(thresholds[column].min()),
            "median": float(thresholds[column].median()),
            "max": float(thresholds[column].max()),
        }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--model", default=MODEL_ID)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--checkpoint-every", type=int, default=DEFAULT_CHECKPOINT_EVERY)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent
    source_finbert = load_data(root / "data/aapl_news_scores.csv")
    source_dates = set(source_finbert.loc[source_finbert["date"].le(END), "date"])
    headlines = load_headlines(args.source, source_dates)
    unique_headlines = headlines[["headline_hash", "headline"]].drop_duplicates(
        "headline_hash"
    ).reset_index(drop=True)

    tokenizer, model, device = prepare_model(args.model)
    validation = validate_constrained_labels(
        root, headlines, tokenizer, model, device, args.batch_size
    )
    print(json.dumps({"constrained_label_validation": validation}, indent=2), flush=True)
    if args.validate_only:
        return

    classified_unique = classify_with_checkpoints(
        root,
        unique_headlines,
        tokenizer,
        model,
        device,
        args.batch_size,
        args.checkpoint_every,
    )
    del model
    if device == "mps":
        torch.mps.empty_cache()

    classified = headlines.merge(
        classified_unique[["headline_hash", "label"]],
        on="headline_hash",
        how="left",
        validate="many_to_one",
    )
    if classified["label"].isna().any():
        raise RuntimeError("Some headlines were not classified")

    grouped_qwen = (
        classified.assign(value=classified["label"].map(LABEL_VALUE))
        .groupby("date")["value"]
        .mean()
    )
    source_qwen = source_finbert.copy()
    source_qwen["news_score"] = source_qwen["date"].map(grouped_qwen).fillna(0.0)

    oos = pd.read_csv(root / "results/oos_daily.csv", parse_dates=["date"])
    oos = oos[oos["date"].le(END)].copy().reset_index(drop=True)
    qwen_oos = oos.copy()
    qwen_oos["news_score"] = qwen_oos["date"].map(grouped_qwen).fillna(0.0)
    qwen_data, qwen_thresholds = attach_training_thresholds(qwen_oos, source_qwen)
    finbert_data, finbert_thresholds = attach_training_thresholds(oos, source_finbert)

    earnings = pd.read_csv(root / "data/aapl_earnings_features.csv", parse_dates=["date"])
    earnings = earnings[earnings["date"].between(oos["date"].min(), oos["date"].max())]
    qwen_daily, qwen_summary, qwen_data = evaluate_model(qwen_data, earnings)
    finbert_daily, finbert_summary, finbert_data = evaluate_model(finbert_data, earnings)
    benchmark_metrics = performance_metrics(oos["market_return"])

    qwen_counts = classified["label"].value_counts().reindex(LABELS, fill_value=0)
    core_test = hac_mean_test(qwen_daily["return"] - finbert_daily["return"])
    analyst_test = hac_mean_test(
        qwen_daily["analyst_return"] - finbert_daily["analyst_return"]
    )
    summary = {
        "period": {
            "start": oos["date"].min().date().isoformat(),
            "end": oos["date"].max().date().isoformat(),
            "matched_oos_days": int(len(oos)),
            "walk_forward_windows": int(oos["window"].nunique()),
            "headline_records": int(len(classified)),
            "unique_anonymized_headlines": int(len(unique_headlines)),
        },
        "comparison_design": {
            "qwen_model": args.model,
            "qwen_device": device,
            "headline_classification": "anonymized headline-only, deterministic, no retrieval",
            "daily_score": "mean of Positive=1, Neutral=0, Negative=-1 labels",
            "model_specific_training_quantiles": [0.25, 0.67, 0.84],
            "threshold_population": "nonzero-news days in each 132-day training window",
            "thresholds_frozen_within_test_fold": True,
            "identical_technical_filters_positions_costs_and_dates": True,
            "transaction_cost_bps_per_unit_turnover": 5.0,
        },
        "constrained_label_validation": validation,
        "qwen_label_counts": {key: int(value) for key, value in qwen_counts.items()},
        "qwen_threshold_distribution": threshold_distribution(qwen_thresholds),
        "finbert_threshold_distribution": threshold_distribution(finbert_thresholds),
        "qwen": qwen_summary,
        "finbert": finbert_summary,
        "aapl_buy_and_hold": benchmark_metrics,
        "paired_qwen_minus_finbert_hac_tests": {
            "core_news": core_test,
            "core_news_plus_analyst": analyst_test,
        },
        "warnings": [
            "Historical development-period comparison, not an untouched holdout.",
            "Qwen3-0.6B is a small local proxy, not Qwen3-4B-Instruct-2507.",
            "Model pretraining may contain historical event knowledge despite entity anonymization.",
            "Technical parameters were inherited from the existing research process rather than recalibrated separately for Qwen.",
        ],
    }

    output = oos[
        ["date", "close", "market_return", "window", "sma", "rsi", "sma_window", "rsi_threshold"]
    ].copy()
    for prefix, daily, enriched in (
        ("qwen", qwen_daily, qwen_data),
        ("finbert", finbert_daily, finbert_data),
    ):
        output[f"{prefix}_score"] = daily["news_score"]
        output[f"{prefix}_bad_threshold"] = enriched["bad_threshold"]
        output[f"{prefix}_moderate_threshold"] = enriched["moderate_threshold"]
        output[f"{prefix}_strong_threshold"] = enriched["strong_threshold"]
        output[f"{prefix}_position"] = daily["position"]
        output[f"{prefix}_turnover"] = daily["turnover"]
        output[f"{prefix}_return"] = daily["return"]
        output[f"{prefix}_equity"] = (1 + daily["return"]).cumprod()
        output[f"{prefix}_analyst_position"] = daily["analyst_position"]
        output[f"{prefix}_analyst_return"] = daily["analyst_return"]
        output[f"{prefix}_analyst_equity"] = (1 + daily["analyst_return"]).cumprod()
    output["benchmark_equity"] = (1 + output["market_return"]).cumprod()

    results = root / "results"
    output.to_csv(results / "full_llm_quantile_daily.csv", index=False)
    classified[["date", "headline_hash", "label"]].to_csv(
        results / "full_llm_quantile_labels.csv", index=False
    )
    qwen_thresholds.to_csv(results / "full_llm_quantile_thresholds.csv", index=False)
    (results / "full_llm_quantile_summary.json").write_text(json.dumps(summary, indent=2))

    plt.figure(figsize=(11, 6))
    plt.plot(output["date"], output["qwen_analyst_equity"], label="Qwen + analyst", linewidth=2)
    plt.plot(output["date"], output["finbert_analyst_equity"], label="FinBERT + analyst", linewidth=2)
    plt.plot(output["date"], output["qwen_equity"], label="Qwen news", alpha=0.8)
    plt.plot(output["date"], output["finbert_equity"], label="FinBERT news", alpha=0.8)
    plt.plot(output["date"], output["benchmark_equity"], label="AAPL buy & hold", alpha=0.65)
    plt.title("Matched-period walk-forward sentiment classifier comparison")
    plt.ylabel("Growth of $1")
    plt.grid(alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(results / "full_llm_quantile_equity.png", dpi=160)
    plt.close()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
