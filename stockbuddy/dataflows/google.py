from typing import Annotated
from datetime import datetime
import os
import yfinance as yf
import requests
from xml.etree.ElementTree import ParseError

from .googlenews_utils import getNewsData
from .hk_stock_names import get_hk_stock_chinese_name
from .news_window_policy import meta_line as _stockbuddy_news_json_line, window_start_date


def get_company_chinese_name(ticker: str) -> str:
    """
    获取公司名称（港股返回中文名，美股返回英文名）
    
    策略：
    1. 对于港股，优先检查硬编码映射表（手动维护，更可靠）
    2. 如果映射表中没有，再使用 yfinance API 获取公司名称
    3. 如果都失败，返回原始 ticker
    
    注意：ticker应该已经经过智能识别系统标准化
    """
    market = os.getenv('DEFAULT_MARKET', 'HK')
    
    # 标准化 ticker 格式
    clean_ticker = ticker.replace('.HK', '').replace('.HKG', '').strip()
    
    if market == 'HKEX' and clean_ticker.isdigit():
        normalized_ticker = f"{clean_ticker.zfill(4)}.HK"
    else:
        normalized_ticker = ticker if '.HK' in ticker or '.' in ticker else ticker
    
    # 对于港股，优先检查硬编码映射表（手动维护，更可靠）
    if market == 'HKEX':
        chinese_name = get_hk_stock_chinese_name(ticker)
        if chinese_name:
            return chinese_name
    
    # 如果映射表中没有，使用 yfinance API
    try:
        ticker_obj = yf.Ticker(normalized_ticker)
        info = ticker_obj.info
        
        if info and info.get('symbol'):
            # 优先返回长名称
            long_name = info.get('longName', '')
            short_name = info.get('shortName', '')
            
            # 对于港股，优先返回中文名称（如果 API 提供）
            if market == 'HKEX':
                # yfinance 有时会返回中文名称，检查是否包含中文字符
                if long_name and any('\u4e00' <= char <= '\u9fff' for char in long_name):
                    return long_name
                elif short_name and any('\u4e00' <= char <= '\u9fff' for char in short_name):
                    return short_name
            
            # 返回英文名称
            if long_name:
                return long_name
            elif short_name:
                return short_name
    except Exception:
        pass
    
    # 最后的 fallback: 返回原始 ticker
    return ticker


def _build_google_news_query(ticker: str) -> str:
    """
    HK numeric codes alone (e.g. 0700) match noise (times, product SKUs). Anchor with
    company + 'Hong Kong stock' + code.hk for RSS q=.
    """
    query = str(ticker)
    default_market = os.getenv("DEFAULT_MARKET", "HK")
    if default_market == "HKEX":
        clean = query.replace(".HK", "").replace(".HKG", "").strip()
        if clean.isdigit():
            code = clean.zfill(4)
            company = get_company_chinese_name(ticker)
            if company and company not in (query, code):
                query = f"{company} {code}.HK Hong Kong stock"
            else:
                query = f"HKEX {code} Hong Kong stock"
        elif "香港" not in query and "Hong Kong" not in query:
            query = f"{query} HK"
    return query.replace(" ", "+")


def _looks_like_hk_numeric_ticker(ticker: str) -> bool:
    c = str(ticker).replace(".HK", "").replace(".HKG", "").strip()
    return c.isdigit() and len(c) <= 5


def _item_passes_hk_relevance(
    item: dict,
    ticker: str,
    company_name: str | None,
) -> bool:
    """Drop RSS rows with no link to code / HK listing / company (minimal, rule-based)."""
    title = item.get("title") or ""
    snip = item.get("snippet") or ""
    link = (item.get("link") or "").lower()
    blob_l = f"{title} {snip} {link}".lower()
    blob_raw = f"{title} {snip} {link}"
    clean = str(ticker).replace(".HK", "").replace(".HKG", "").strip()
    if not clean.isdigit():
        return True
    noise = (
        "national weather service",
        "weather.gov",
        "noaa",
        "snowfall",
        "snow storm",
        "winter storm",
    )
    if any(n in blob_l for n in noise):
        return False
    code = clean.zfill(4)
    if f"{code}.hk" in blob_l or f"hk:{code}" in blob_l or "hkex" in blob_l:
        return True
    if "hong kong" in blob_l and code in blob_l.replace(".", ""):
        return True
    if company_name and company_name not in (ticker, clean, code):
        if company_name in blob_raw:
            return True
        cjk = "".join(c for c in company_name if "\u4e00" <= c <= "\u9fff")
        if len(cjk) >= 2 and cjk[:2] in blob_raw:
            return True
        if "腾" in company_name and "tencent" in blob_l:
            return True
        if "阿里" in company_name and "alibaba" in blob_l:
            return True
        if "友邦" in company_name and ("aia" in blob_l or "友邦" in blob_raw):
            return True
    return False


def get_google_news(
    ticker: Annotated[str, "Ticker symbol"],
    start_date: Annotated[str, "Start date yyyy-mm-dd"],
    end_date: Annotated[str, "End date yyyy-mm-dd"],
) -> str:
    """
    Google News RSS for [start_date, end_date]. First line is STOCKBUDDY_NEWS_JSON
    with status ok|empty_window|provider_error|parse_error (no silent fake articles).
    """
    query = _build_google_news_query(ticker)
    try:
        datetime.strptime(start_date, "%Y-%m-%d")
        datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError as e:
        return (
            _stockbuddy_news_json_line(
                {
                    "status": "parse_error",
                    "provider": "google_rss",
                    "detail": str(e)[:200],
                }
            )
            + "\n\nInvalid date format; expected yyyy-mm-dd (no fabricated news body)."
        )

    try:
        news_results = getNewsData(query, start_date, end_date)
    except requests.RequestException as e:
        return (
            _stockbuddy_news_json_line(
                {
                    "status": "provider_error",
                    "provider": "google_rss",
                    "detail": str(e)[:200],
                }
            )
            + "\n\nRSS HTTP/request failed (no fabricated articles)."
        )
    except ParseError as e:
        return (
            _stockbuddy_news_json_line(
                {
                    "status": "parse_error",
                    "provider": "google_rss",
                    "detail": str(e)[:200],
                }
            )
            + "\n\nRSS XML parse failed (no fabricated articles)."
        )
    except ValueError as e:
        return (
            _stockbuddy_news_json_line(
                {
                    "status": "parse_error",
                    "provider": "google_rss",
                    "detail": str(e)[:200],
                }
            )
            + "\n\nRSS date/window parse failed (no fabricated articles)."
        )
    except Exception as e:
        return (
            _stockbuddy_news_json_line(
                {
                    "status": "provider_error",
                    "provider": "google_rss",
                    "detail": str(e)[:200],
                }
            )
            + "\n\nUnexpected RSS pipeline error (no fabricated articles)."
        )

    raw_rss_count = len(news_results)
    default_market = os.getenv("DEFAULT_MARKET", "HK")
    # Apply HK relevance whenever ticker is a numeric HK-style code (env may be HK not HKEX).
    if default_market == "HKEX" or _looks_like_hk_numeric_ticker(ticker):
        cn = get_company_chinese_name(ticker)
        news_results = [
            it
            for it in news_results
            if _item_passes_hk_relevance(it, ticker, cn)
        ]

    if not news_results:
        meta = {
            "status": "empty_window",
            "provider": "google_rss",
            "count": 0,
            "window": f"{start_date}..{end_date}",
            "raw_rss_count": raw_rss_count,
            "relevance_filtered": raw_rss_count > 0,
        }
        msg = (
            "No RSS items in the requested date window after filtering "
            "(not a placeholder article)."
        )
        if raw_rss_count > 0:
            msg = (
                "RSS returned items but none passed HK relevance filter "
                "(code/company/HKEX/Tencent-style checks; not a placeholder article)."
            )
        return _stockbuddy_news_json_line(meta) + f"\n\n{msg}"

    lines = []
    for news in news_results:
        title = str(news.get("title", ""))
        src = str(news.get("source", ""))
        snip = str(news.get("snippet", ""))
        lines.append(f"### {title} (source: {src}) \n\n{snip}\n\n")

    body = "".join(lines)
    q_disp = query.replace("+", " ")
    meta = {
        "status": "ok",
        "provider": "google_rss",
        "count": len(news_results),
        "window": f"{start_date}..{end_date}",
        "raw_rss_count": raw_rss_count,
        "relevance_filtered": len(news_results) < raw_rss_count,
    }
    header = _stockbuddy_news_json_line(meta)
    return (
        f"{header}\n\n## {q_disp} Google News, from {start_date} to {end_date}:\n\n{body}"
    )


def _build_google_global_query() -> str:
    return "macroeconomics+OR+Federal+Reserve+OR+Hang+Seng+OR+Hong+Kong+stocks+OR+利率"


def get_google_global_news(
    start_date: Annotated[str, "Start yyyy-mm-dd"],
    end_date: Annotated[str, "End yyyy-mm-dd"],
    limit: int = 10,
) -> str:
    """
    Google News RSS for macro/global window [start_date, end_date].
    Same STOCKBUDDY_NEWS_JSON header as get_google_news; scope=global.
    """
    query = _build_google_global_query()
    try:
        datetime.strptime(start_date, "%Y-%m-%d")
        datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError as e:
        return (
            _stockbuddy_news_json_line(
                {
                    "status": "parse_error",
                    "scope": "global",
                    "provider": "google_rss_global",
                    "detail": str(e)[:200],
                }
            )
            + "\n\nInvalid date format (no fabricated body)."
        )

    try:
        news_results = getNewsData(query, start_date, end_date)
    except requests.RequestException as e:
        return (
            _stockbuddy_news_json_line(
                {
                    "status": "provider_error",
                    "scope": "global",
                    "provider": "google_rss_global",
                    "detail": str(e)[:200],
                }
            )
            + "\n\nRSS request failed (no fabricated articles)."
        )
    except ParseError as e:
        return (
            _stockbuddy_news_json_line(
                {
                    "status": "parse_error",
                    "scope": "global",
                    "provider": "google_rss_global",
                    "detail": str(e)[:200],
                }
            )
            + "\n\nRSS XML parse failed (no fabricated articles)."
        )
    except ValueError as e:
        return (
            _stockbuddy_news_json_line(
                {
                    "status": "parse_error",
                    "scope": "global",
                    "provider": "google_rss_global",
                    "detail": str(e)[:200],
                }
            )
            + "\n\nRSS window parse failed (no fabricated articles)."
        )
    except Exception as e:
        return (
            _stockbuddy_news_json_line(
                {
                    "status": "provider_error",
                    "scope": "global",
                    "provider": "google_rss_global",
                    "detail": str(e)[:200],
                }
            )
            + "\n\nUnexpected RSS error (no fabricated articles)."
        )

    raw_rss_count = len(news_results)
    if limit > 0:
        news_results = news_results[: int(limit)]

    if not news_results:
        meta = {
            "status": "empty_window",
            "scope": "global",
            "provider": "google_rss_global",
            "count": 0,
            "window": f"{start_date}..{end_date}",
            "raw_rss_count": raw_rss_count,
        }
        return (
            _stockbuddy_news_json_line(meta)
            + "\n\nNo RSS items in the requested global window (not placeholder text)."
        )

    lines = []
    for news in news_results:
        title = str(news.get("title", ""))
        src = str(news.get("source", ""))
        snip = str(news.get("snippet", ""))
        lines.append(f"### {title} (source: {src}) \n\n{snip}\n\n")

    body = "".join(lines)
    meta = {
        "status": "ok",
        "scope": "global",
        "provider": "google_rss_global",
        "count": len(news_results),
        "window": f"{start_date}..{end_date}",
        "raw_rss_count": raw_rss_count,
    }
    header = _stockbuddy_news_json_line(meta)
    return (
        f"{header}\n\n## Global macro Google News, {start_date} to {end_date}:\n\n{body}"
    )


def get_google_global_news_tool(
    curr_date: Annotated[str, "Anchor yyyy-mm-dd"],
    look_back_days: int = 7,
    limit: int = 5,
) -> str:
    """LangChain tool shape: window [curr-lookback, curr] inclusive."""
    cd = str(curr_date).strip()
    sd = window_start_date(cd, look_back_days)
    return get_google_global_news(sd, cd, limit)
