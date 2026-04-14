"""
Google News: RSS search (no JS). HTML /search?tbm=nws often returns JS-only shell for bots.
"""

from __future__ import annotations

import html as html_lib
import os
import re
import time
import random
import urllib.parse
from datetime import date, datetime
from typing import Tuple
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET

import requests


def _parse_input_dates(start_date: str, end_date: str) -> Tuple[date, date]:
    for fmt, s, e in [
        ("%Y-%m-%d", start_date, end_date),
        ("%m/%d/%Y", start_date, end_date),
    ]:
        try:
            return (
                datetime.strptime(s.strip(), fmt).date(),
                datetime.strptime(e.strip(), fmt).date(),
            )
        except ValueError:
            continue
    raise ValueError(f"bad date range: {start_date!r} {end_date!r}")


def _strip_html(s: str) -> str:
    t = html_lib.unescape(s or "")
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def getNewsData(query: str, start_date: str, end_date: str) -> list[dict]:
    """
    Google News via RSS. query may use '+' for spaces (from _build_google_news_query).

    Returns:
        list of dict: title, link, snippet, date, source
    """
    q = query.replace("+", " ").strip()
    hl = os.getenv("GOOGLE_NEWS_RSS_HL", "en-HK")
    gl = os.getenv("GOOGLE_NEWS_RSS_GL", "HK")
    ceid = os.getenv("GOOGLE_NEWS_RSS_CEID", "HK:en")
    params = urllib.parse.urlencode({"q": q, "hl": hl, "gl": gl, "ceid": ceid})
    url = f"https://news.google.com/rss/search?{params}"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": "application/rss+xml, application/xml, text/xml, */*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,zh-TW;q=0.8",
    }
    time.sleep(random.uniform(0.3, 1.0))
    r = requests.get(url, headers=headers, timeout=25)
    r.raise_for_status()

    root = ET.fromstring(r.content)
    sd, ed = _parse_input_dates(start_date, end_date)
    if sd > ed:
        sd, ed = ed, sd

    news_results: list[dict] = []
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub_raw = (item.findtext("pubDate") or "").strip()
        desc = (item.findtext("description") or "").strip()
        src_el = item.find("source")
        source = (src_el.text or "").strip() if src_el is not None else "Unknown"

        snippet = _strip_html(desc)[:800] or title
        pub_disp = pub_raw
        try:
            dt = parsedate_to_datetime(pub_raw)
            d = dt.date()
        except (TypeError, ValueError):
            d = None

        if d is not None and (d < sd or d > ed):
            continue

        if not title:
            continue

        news_results.append(
            {
                "link": link,
                "title": title,
                "snippet": snippet,
                "date": pub_disp,
                "source": source,
            }
        )

    return news_results
