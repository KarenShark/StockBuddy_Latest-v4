"""
target_eval_v1 — draft protocol (with news). Separate from formal_eval_v1 (no-news).

Do not merge batches/metrics with formal_eval_v1. Keep analysts/tables isolated.
Mirror dates/tickers with formal_eval_v1 manually when that protocol changes.
"""

from __future__ import annotations

from typing import List, Tuple

TARGET_EVAL_V1_PROTOCOL_ID = "target_eval_v1_draft_v0"
TARGET_EVAL_V1_NEWS_PROVIDER = "google_rss"

TARGET_EVAL_V1_TICKERS: List[str] = ["0700", "1299", "0941", "0388", "9988"]

TARGET_EVAL_V1_PERIOD_START = "2024-06-01"
TARGET_EVAL_V1_PERIOD_END = "2024-08-31"

TARGET_EVAL_V1_ANALYSIS_DATES_ISO: List[str] = [
    "2024-06-03",
    "2024-07-02",
    "2024-08-01",
]

# market + fundamentals + news (Google RSS via get_news when tool_vendors allow)
TARGET_EVAL_V1_ANALYSTS: List[str] = ["market", "fundamentals", "news"]

TARGET_EVAL_V1_PROFILES: Tuple[str, ...] = (
    "buy_and_hold",
    "single_agent",
    "full_system",
)
