"""EODHD historical news + per-article sentiment for HK stocks."""

from __future__ import annotations

import json
import os
import time
from typing import Annotated

import requests

from .news_window_policy import STOCKBUDDY_NEWS_JSON_PREFIX

_EODHD_NEWS_URL = "https://eodhd.com/api/news"
_last_call_ts: float = 0.0


def _rate_limit() -> None:
    global _last_call_ts
    elapsed = time.monotonic() - _last_call_ts
    if elapsed < 1.1:
        time.sleep(1.1 - elapsed)
    _last_call_ts = time.monotonic()


def _norm_eodhd_symbol(ticker: str) -> str:
    """'0700' / '9988.HK' -> '0700.HK'"""
    c = str(ticker).replace(".HK", "").replace(".HKG", "").strip()
    if c.isdigit():
        return f"{c.zfill(4)}.HK"
    return f"{c}.HK"


def get_eodhd_news(
    ticker: Annotated[str, "Ticker, e.g. '0700' or '9988.HK'"],
    start_date: Annotated[str, "yyyy-mm-dd"],
    end_date: Annotated[str, "yyyy-mm-dd"],
) -> str:
    """Fetch historical news + per-article sentiment from EODHD.
    Returns STOCKBUDDY_NEWS_JSON header + markdown body."""
    api_key = (os.getenv("EODHD_API_KEY") or "").strip()
    if not api_key:
        meta = {
            "status": "skipped",
            "provider": "eodhd",
            "count": 0,
            "reason": "no EODHD_API_KEY",
        }
        return STOCKBUDDY_NEWS_JSON_PREFIX + json.dumps(meta) + "\n\nNo EODHD API key."

    symbol = _norm_eodhd_symbol(ticker)
    _rate_limit()

    try:
        resp = requests.get(
            _EODHD_NEWS_URL,
            params={
                "s": symbol,
                "from": start_date,
                "to": end_date,
                "api_token": api_key,
                "fmt": "json",
                "limit": 50,
            },
            timeout=15,
        )
        resp.raise_for_status()
        articles = resp.json()
    except requests.RequestException as e:
        meta = {
            "status": "provider_error",
            "provider": "eodhd",
            "count": 0,
            "detail": str(e)[:300],
        }
        return (
            STOCKBUDDY_NEWS_JSON_PREFIX
            + json.dumps(meta)
            + f"\n\nEODHD request failed: {e}"
        )

    if not isinstance(articles, list):
        meta = {
            "status": "provider_error",
            "provider": "eodhd",
            "count": 0,
            "detail": f"unexpected type: {type(articles).__name__}",
        }
        return (
            STOCKBUDDY_NEWS_JSON_PREFIX
            + json.dumps(meta)
            + "\n\nEODHD returned unexpected format."
        )

    lines: list[str] = []
    sent_agg = {"pos_sum": 0.0, "neg_sum": 0.0, "n": 0}

    for art in articles:
        title = (art.get("title") or "").strip()
        if not title:
            continue
        content = (art.get("content") or "").strip()
        date_str = art.get("date") or ""
        link = art.get("link") or ""
        tags = art.get("tags") or []
        sent = art.get("sentiment") or {}

        polarity = sent.get("polarity")
        pos = sent.get("pos", 0)
        neg = sent.get("neg", 0)

        if polarity is not None:
            label = "positive" if polarity > 0.1 else ("negative" if polarity < -0.1 else "neutral")
            sent_line = f"**Sentiment**: {label} (polarity={polarity:.3f}, pos={pos:.2f}, neg={neg:.2f})"
            sent_agg["pos_sum"] += pos
            sent_agg["neg_sum"] += neg
            sent_agg["n"] += 1
        else:
            sent_line = ""

        snippet = content[:500] + ("..." if len(content) > 500 else "")

        block = f"### {title}\n\n**Date**: {date_str}"
        if tags:
            block += f"  |  **Tags**: {', '.join(tags[:5])}"
        block += "\n"
        if sent_line:
            block += f"{sent_line}\n"
        if snippet:
            block += f"\n{snippet}\n"
        if link:
            block += f"\n{link}\n"
        lines.append(block)

    n = len(lines)
    avg_pos = round(sent_agg["pos_sum"] / sent_agg["n"], 3) if sent_agg["n"] else None
    avg_neg = round(sent_agg["neg_sum"] / sent_agg["n"], 3) if sent_agg["n"] else None

    meta = {
        "status": "ok" if n > 0 else "empty_window",
        "provider": "eodhd",
        "count": n,
        "window": f"{start_date}..{end_date}",
        "symbol_queried": symbol,
        "sentiment_summary": {
            "articles_with_sentiment": sent_agg["n"],
            "avg_positive": avg_pos,
            "avg_negative": avg_neg,
        },
    }

    header = STOCKBUDDY_NEWS_JSON_PREFIX + json.dumps(meta, ensure_ascii=False)
    if not lines:
        return header + f"\n\nNo EODHD articles for {symbol} in {start_date}..{end_date}."

    body = "\n\n".join(lines)
    return f"{header}\n\n## EODHD News ({symbol}), {start_date} to {end_date}\n\n{body}"
