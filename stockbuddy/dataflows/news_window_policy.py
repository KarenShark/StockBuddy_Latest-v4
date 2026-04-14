"""Shared news JSON header + historical window (UTC end < today)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

STOCKBUDDY_NEWS_JSON_PREFIX = "STOCKBUDDY_NEWS_JSON:"


def meta_line(meta: dict) -> str:
    return STOCKBUDDY_NEWS_JSON_PREFIX + json.dumps(meta, ensure_ascii=False)


def parse_leading_meta(block: str) -> tuple[dict | None, str]:
    if not block or not block.startswith(STOCKBUDDY_NEWS_JSON_PREFIX):
        return None, block
    line, sep, rest = block.partition("\n")
    raw = line[len(STOCKBUDDY_NEWS_JSON_PREFIX) :]
    try:
        return json.loads(raw), rest if sep else ""
    except json.JSONDecodeError:
        return None, block


def analysis_end_is_historical(end_date_yyyy_mm_dd: str) -> bool:
    end_d = datetime.strptime(end_date_yyyy_mm_dd.strip(), "%Y-%m-%d").date()
    today = datetime.now(timezone.utc).date()
    return end_d < today


def window_start_date(end_date_yyyy_mm_dd: str, look_back_days: int) -> str:
    ed = datetime.strptime(end_date_yyyy_mm_dd.strip(), "%Y-%m-%d")
    sd = ed - timedelta(days=int(look_back_days))
    return sd.strftime("%Y-%m-%d")
