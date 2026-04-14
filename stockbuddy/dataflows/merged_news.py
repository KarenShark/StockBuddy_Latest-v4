"""Multi-source company news: Google RSS + yfinance stream + EODHD (historical) + optional Newsdata.io."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Annotated

import yfinance as yf

from .eodhd_news import get_eodhd_news
from .google import (
    _item_passes_hk_relevance,
    _looks_like_hk_numeric_ticker,
    get_company_chinese_name,
    get_google_news,
)
from .hk_stock_names import get_hk_stock_chinese_name
from .news_window_policy import analysis_end_is_historical, parse_leading_meta
from .newsdata_io import get_newsdata_hk_stock_news

_STOCKBUDDY_PREFIX = "STOCKBUDDY_NEWS_JSON:"


def _norm_hk_yf_symbol(ticker: str) -> str:
    c = str(ticker).replace(".HK", "").replace(".HKG", "").strip()
    if c.isdigit():
        return f"{c.zfill(4)}.HK"
    return str(ticker)


def _parse_iso_date(d: str) -> datetime:
    return datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def _split_google_block(out: str) -> tuple[dict | None, str]:
    line0, _, rest = out.partition("\n")
    line0 = line0.strip()
    if not line0.startswith(_STOCKBUDDY_PREFIX):
        return None, out.strip()
    try:
        meta = json.loads(line0[len(_STOCKBUDDY_PREFIX) :])
    except json.JSONDecodeError:
        return None, out.strip()
    return meta, rest.strip()


def _title_fingerprint(title: str) -> str:
    t = re.sub(r"\s+", " ", (title or "").strip().lower())
    return t[:120] if t else ""


def _yfinance_news_section(
    ticker: str, start_date: str, end_date: str, seen: set[str]
) -> tuple[str, int]:
    sym = _norm_hk_yf_symbol(ticker)
    start_d = _parse_iso_date(start_date).date()
    end_d = _parse_iso_date(end_date).date()
    try:
        items = yf.Ticker(sym).news or []
    except Exception:
        return "", 0
    lines: list[str] = []
    n = 0
    for row in items:
        c = row.get("content") or {}
        title = c.get("title") or ""
        pub = c.get("pubDate") or c.get("displayTime") or ""
        if not title or not pub:
            continue
        try:
            pdt = datetime.fromisoformat(str(pub).replace("Z", "+00:00")).date()
        except ValueError:
            continue
        if not (start_d <= pdt <= end_d):
            continue
        fp = _title_fingerprint(title)
        if fp in seen:
            continue
        seen.add(fp)
        src = (c.get("provider") or {}).get("displayName") or "yfinance"
        summ = (c.get("summary") or "").strip()
        url = ""
        cu = c.get("canonicalUrl") or c.get("clickThroughUrl")
        if isinstance(cu, dict):
            url = cu.get("url") or ""
        if _looks_like_hk_numeric_ticker(ticker):
            cn = get_company_chinese_name(ticker)
            if not _item_passes_hk_relevance(
                {"title": title, "snippet": summ, "link": url}, ticker, cn
            ):
                continue
        lines.append(f"### {title} (source: {src}, {pdt.isoformat()})\n\n{summ}\n")
        if url:
            lines.append(f"\n{url}\n")
        lines.append("\n")
        n += 1
    if not lines:
        return "", 0
    body = "".join(lines)
    return (
        f"## yfinance / Yahoo stream ({sym}), {start_date} to {end_date}\n\n{body}",
        n,
    )


def _google_titles_into_seen(google_body: str, seen: set[str]) -> None:
    for m in re.finditer(r"^###\s+(.+?)\s+\(source:", google_body, re.MULTILINE):
        seen.add(_title_fingerprint(m.group(1)))


def _newsdata_section(ticker: str, start_date: str, end_date: str) -> tuple[str, dict]:
    if not (os.getenv("NEWSDATA_API_KEY") or "").strip():
        return "", {"skipped": True, "reason": "no NEWSDATA_API_KEY", "count": 0}
    start_d = _parse_iso_date(start_date).date()
    end_d = _parse_iso_date(end_date).date()
    days_back = max(1, min(30, (end_d - start_d).days + 1))
    code = str(ticker).replace(".HK", "").replace(".HKG", "").strip()
    company = get_hk_stock_chinese_name(ticker) or ""
    try:
        raw = get_newsdata_hk_stock_news(code, company, days_back=days_back, max_results=10)
    except Exception as e:
        return "", {"skipped": False, "error": str(e)[:200], "count": 0}
    if not raw or raw.startswith("❌") or raw.startswith("⚠️"):
        return "", {"skipped": False, "count": 0, "note": "no_results_or_api_error"}
    cnt = len(re.findall(r"^##\s+\d+\.\s", raw, re.MULTILINE))
    body = "## Newsdata.io (zh, cn/hk/tw)\n\n" + raw
    return body, {"skipped": False, "count": cnt}


def _eodhd_section(ticker: str, start_date: str, end_date: str) -> tuple[str, dict]:
    """Call EODHD and return (markdown_body, info_dict)."""
    if not (os.getenv("EODHD_API_KEY") or "").strip():
        return "", {"skipped": True, "reason": "no EODHD_API_KEY", "count": 0}
    try:
        raw = get_eodhd_news(ticker, start_date, end_date)
    except Exception as e:
        return "", {"skipped": False, "error": str(e)[:200], "count": 0}
    meta, body = parse_leading_meta(raw)
    if not meta:
        return "", {"skipped": False, "count": 0, "note": "parse_fail"}
    cnt = int(meta.get("count") or 0)
    info = {
        "skipped": False,
        "count": cnt,
        "status": meta.get("status"),
        "sentiment_summary": meta.get("sentiment_summary"),
    }
    return body.strip(), info


def get_merged_stock_news(
    ticker: Annotated[str, "Ticker symbol"],
    start_date: Annotated[str, "Start date yyyy-mm-dd"],
    end_date: Annotated[str, "End date yyyy-mm-dd"],
) -> str:
    """
    Google RSS (filtered) + yfinance news stream + EODHD (historical) + optional Newsdata.io.
    First line STOCKBUDDY_NEWS_JSON with provider=merged and per-source counts.
    """
    historical = analysis_end_is_historical(end_date)
    seen: set[str] = set()

    google_out = get_google_news(ticker, start_date, end_date)
    g_meta, g_body = _split_google_block(google_out)
    g_count = int((g_meta or {}).get("count") or 0)
    if g_body:
        _google_titles_into_seen(g_body, seen)

    y_sec, y_n = _yfinance_news_section(ticker, start_date, end_date, seen)

    # EODHD: primary historical news source (has date-bounded archive + sentiment)
    if historical:
        eodhd_sec, eodhd_info = _eodhd_section(ticker, start_date, end_date)
    else:
        eodhd_sec, eodhd_info = "", {"skipped": True, "reason": "not_historical", "count": 0}

    # Newsdata.io: only for recent dates (free tier has no archive)
    if historical:
        nd_sec, nd_info = "", {
            "skipped": True,
            "reason": "historical_mode_newsdata_unbounded",
            "count": 0,
        }
    else:
        nd_sec, nd_info = _newsdata_section(ticker, start_date, end_date)

    parts: list[str] = []
    gb = (g_body or "").strip()
    parts.append(f"## Google RSS\n\n{gb if gb else '_(no body)_'}")

    if y_sec:
        parts.append(y_sec)
    if eodhd_sec:
        parts.append(eodhd_sec)
    if nd_sec:
        parts.append(nd_sec)

    eodhd_count = int(eodhd_info.get("count") or 0)
    nd_count = int(nd_info.get("count") or 0)
    total_items = g_count + y_n + eodhd_count + nd_count

    has_substance = (
        ((g_meta or {}).get("status") == "ok" and g_count > 0)
        or y_n > 0
        or eodhd_count > 0
        or nd_count > 0
    )
    st = "ok" if has_substance else "empty_window"

    merged_meta = {
        "status": st,
        "provider": "merged",
        "count": total_items,
        "window": f"{start_date}..{end_date}",
        "google_rss": g_meta,
        "yfinance": {"count": y_n},
        "eodhd": eodhd_info,
        "newsdata": nd_info,
    }
    header = _STOCKBUDDY_PREFIX + json.dumps(merged_meta, ensure_ascii=False)
    if not parts:
        msg = "No articles from merged sources in this window."
        return header + f"\n\n{msg}"

    body = "\n\n---\n\n".join(parts)
    return f"{header}\n\n# Merged company news ({start_date} .. {end_date})\n\n{body}"
