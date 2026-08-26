"""Small local-LLM replacement test for the daily FinBERT news score.

This diagnostic deliberately reuses the frozen core-plus-news trading rule. It
changes only the headline sentiment classifier, allowing a like-for-like test
against the existing FinBERT daily score over a short historical window.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from quick_core_overlay import build_overlay_positions
from run_backtest import DATA_END
from strategy import performance_metrics


MODEL_ID = "Qwen/Qwen3-0.6B"
START = pd.Timestamp("2024-10-01")
END = DATA_END
COST_PER_TURNOVER = 5 / 10_000
DEFAULT_SOURCE = Path("data/apple_news_data.csv")
LABELS = ("Positive", "Negative", "Neutral")


def anonymize_headline(value: object) -> str:
    """Reduce the chance that model memory of a named Apple event drives a label."""
    text = str(value).replace("\\n", " ").strip()
    replacements = {
        r"\bApple(?:'s)?\b": "Company A",
        r"\bAAPL\b": "Company A",
        r"\biPhone\b": "flagship phone",
        r"\biPad\b": "tablet product",
        r"\bMac(?:Book)?\b": "computer product",
        r"\bTim Cook\b": "the chief executive",
    }
    for pattern, replacement in replacements.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text)[:400]


def load_headlines(source: Path, trading_dates: set[pd.Timestamp]) -> pd.DataFrame:
    news = pd.read_csv(source, usecols=["date", "title"])
    news["date"] = pd.to_datetime(news["date"], utc=True, errors="coerce").dt.tz_localize(None).dt.normalize()
    news = news[news["date"].isin(trading_dates)].dropna(subset=["date", "title"])
    news["headline"] = news["title"].map(anonymize_headline)
    news = news[news["headline"].str.len().gt(0)].drop_duplicates(["date", "headline"])
    news["headline_hash"] = news["headline"].map(
        lambda value: hashlib.sha256(value.encode("utf-8")).hexdigest()
    )
    return news[["date", "headline", "headline_hash"]].reset_index(drop=True)


def build_prompts(tokenizer: AutoTokenizer, headlines: list[str]) -> list[str]:
    prompts: list[str] = []
    for headline in headlines:
        messages = [
            {
                "role": "system",
                "content": (
                    "Classify the investor sentiment toward Company A using only the "
                    "headline. Positive means clearly favorable for valuation, earnings, "
                    "demand, or risk; Negative means clearly unfavorable; Neutral means "
                    "mixed, descriptive, unrelated, or insufficient. Reply with exactly "
                    "one word: Positive, Negative, or Neutral."
                ),
            },
            {
                "role": "user",
                "content": "Company A cuts its outlook as demand falls sharply",
            },
            {"role": "assistant", "content": "Negative"},
            {
                "role": "user",
                "content": "Company A reports record profit and raises its outlook",
            },
            {"role": "assistant", "content": "Positive"},
            {
                "role": "user",
                "content": "Company A schedules its annual shareholder meeting",
            },
            {"role": "assistant", "content": "Neutral"},
            {"role": "user", "content": headline},
        ]
        try:
            prompt = tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=False,
            )
        except TypeError:
            prompt = tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
        prompts.append(prompt)
    return prompts


def classify_headlines(
    headlines: list[str], model_id: str, batch_size: int
) -> tuple[list[str], str]:
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    tokenizer.padding_side = "left"
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token_id = tokenizer.eos_token_id

    dtype = torch.float16 if device == "mps" else torch.float32
    model = AutoModelForCausalLM.from_pretrained(model_id, torch_dtype=dtype)
    model.to(device)
    model.eval()

    labels: list[str] = []
    prompts = build_prompts(tokenizer, headlines)
    for start in range(0, len(prompts), batch_size):
        batch = prompts[start : start + batch_size]
        encoded = tokenizer(
            batch,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=256,
        ).to(device)
        with torch.inference_mode():
            generated = model.generate(
                **encoded,
                max_new_tokens=3,
                do_sample=False,
                pad_token_id=tokenizer.pad_token_id,
            )
        new_tokens = generated[:, encoded["input_ids"].shape[1] :]
        outputs = tokenizer.batch_decode(new_tokens, skip_special_tokens=True)
        for output in outputs:
            match = re.search(r"\b(Positive|Negative|Neutral)\b", output, re.IGNORECASE)
            labels.append(match.group(1).title() if match else "Neutral")
        print(f"Classified {min(start + batch_size, len(prompts))}/{len(prompts)} headlines")
    return labels, device


def daily_scores(classified: pd.DataFrame, dates: pd.Series) -> pd.Series:
    values = classified["label"].map({"Positive": 1.0, "Negative": -1.0, "Neutral": 0.0})
    grouped = values.groupby(classified["date"]).mean()
    return dates.map(grouped).fillna(0.0).astype(float)


def evaluate_variant(data: pd.DataFrame, score: pd.Series) -> tuple[pd.DataFrame, dict]:
    lagged_news = score.shift(1)
    long_filter = (data["close"] > data["sma"]) & (data["rsi"] > data["rsi_threshold"])
    short_filter = (data["close"] < data["sma"]) & (
        data["rsi"] < (100 - data["rsi_threshold"])
    )
    long_events = (lagged_news < -0.05) & long_filter
    moderate_events = (lagged_news > 0.20) & (lagged_news <= 0.30) & short_filter
    strong_events = (lagged_news > 0.30) & short_filter
    positions = build_overlay_positions(long_events, moderate_events, strong_events)
    turnover = positions.diff().abs()
    turnover.iloc[0] = abs(positions.iloc[0])
    returns = positions * data["market_return"] - turnover * COST_PER_TURNOVER
    metrics = performance_metrics(returns, positions=positions, turnover=turnover)
    metrics.update(
        {
            "negative_news_events": int(long_events.sum()),
            "moderate_short_events": int(moderate_events.sum()),
            "strong_short_events": int(strong_events.sum()),
            "days_at_core_0.5": int(positions.eq(0.5).sum()),
            "days_at_long_1.0": int(positions.eq(1.0).sum()),
            "days_at_short_minus_1.0": int(positions.eq(-1.0).sum()),
        }
    )
    return pd.DataFrame({"position": positions, "return": returns}), metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--model", default=MODEL_ID)
    parser.add_argument("--batch-size", type=int, default=12)
    args = parser.parse_args()

    root = Path(__file__).resolve().parent
    full = pd.read_csv(root / "results/oos_daily.csv", parse_dates=["date"])
    data = full[full["date"].between(START, END)].copy().reset_index(drop=True)
    headlines = load_headlines(args.source, set(data["date"]))
    labels, device = classify_headlines(headlines["headline"].tolist(), args.model, args.batch_size)
    headlines["label"] = labels

    llm_score = daily_scores(headlines, data["date"])
    finbert_score = data["news_score"].astype(float)
    llm, llm_metrics = evaluate_variant(data, llm_score)
    finbert, finbert_metrics = evaluate_variant(data, finbert_score)

    core_position = pd.Series(0.5, index=data.index)
    core_turnover = core_position.diff().abs()
    core_turnover.iloc[0] = 0.5
    core_return = core_position * data["market_return"] - core_turnover * COST_PER_TURNOVER
    benchmark_metrics = performance_metrics(data["market_return"])
    core_metrics = performance_metrics(core_return, positions=core_position, turnover=core_turnover)

    label_counts = headlines["label"].value_counts().reindex(LABELS, fill_value=0)
    summary = {
        "period": {
            "start": START.date().isoformat(),
            "end": END.date().isoformat(),
            "trading_days": int(len(data)),
            "headlines": int(len(headlines)),
        },
        "llm": {
            "model": args.model,
            "device": device,
            "classification": "anonymized headline-only, deterministic, no retrieval",
            "label_counts": {key: int(value) for key, value in label_counts.items()},
            "unparsed_outputs_defaulted_to_neutral": 0,
        },
        "frozen_strategy": {
            "normal_position": 0.5,
            "negative_news_recovery": "score < -0.05, then 100% long for 1 day",
            "moderate_short": "0.20 < score <= 0.30, then short for 1 day",
            "strong_short": "score > 0.30, then short for 3 days",
            "technical_filters": True,
            "short_priority": True,
            "transaction_cost_bps_per_unit_turnover": 5.0,
        },
        "qwen3_0_6b_overlay": llm_metrics,
        "finbert_overlay_same_window": finbert_metrics,
        "passive_50_percent_aapl": core_metrics,
        "aapl_buy_and_hold": benchmark_metrics,
        "warnings": [
            "Short development diagnostic; not an untouched holdout.",
            "Qwen3-0.6B is a fast local proxy, not Qwen3-4B-Instruct-2507.",
            "The model predates this historical window and may retain event knowledge despite entity anonymization.",
        ],
    }

    output = data[["date", "close", "market_return"]].copy()
    output["finbert_score"] = finbert_score
    output["qwen_score"] = llm_score
    output["qwen_position"] = llm["position"]
    output["qwen_return"] = llm["return"]
    output["qwen_equity"] = (1 + llm["return"]).cumprod()
    output["finbert_position"] = finbert["position"]
    output["finbert_return"] = finbert["return"]
    output["finbert_equity"] = (1 + finbert["return"]).cumprod()
    output["core_equity"] = (1 + core_return).cumprod()
    output["benchmark_equity"] = (1 + data["market_return"]).cumprod()

    results = root / "results"
    results.mkdir(exist_ok=True)
    output.to_csv(results / "quick_llm_news_daily.csv", index=False)
    headlines[["date", "headline_hash", "label"]].to_csv(
        results / "quick_llm_news_labels.csv", index=False
    )
    (results / "quick_llm_news_summary.json").write_text(json.dumps(summary, indent=2))

    plt.figure(figsize=(10, 5.5))
    plt.plot(output["date"], output["qwen_equity"], label="Qwen3-0.6B overlay", linewidth=2)
    plt.plot(output["date"], output["finbert_equity"], label="FinBERT overlay")
    plt.plot(output["date"], output["core_equity"], label="Passive 50% AAPL")
    plt.plot(output["date"], output["benchmark_equity"], label="AAPL buy & hold", alpha=0.7)
    plt.title("Local LLM news diagnostic: Oct 1–Nov 27, 2024")
    plt.ylabel("Growth of $1")
    plt.grid(alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(results / "quick_llm_news_equity.png", dpi=160)
    plt.close()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
