"""
Price helpers: HK ticker for yfinance, trading-day index from history.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import List, Optional, Tuple

import pandas as pd
import yfinance as yf


def normalize_hk_symbol(ticker: str) -> str:
    t = ticker.strip().upper().replace(".HKG", ".HK")
    if t.endswith(".HK"):
        return t
    core = t.replace(".HK", "")
    if core.isdigit():
        return f"{core.zfill(4)}.HK"
    return t


def fetch_ohlc(symbol: str, start: date, end: date) -> pd.DataFrame:
    """Daily bars; index normalized to date (UTC stripped)."""
    tkr = yf.Ticker(symbol)
    df = tkr.history(start=start.isoformat(), end=(end + timedelta(days=1)).isoformat())
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    out.index = pd.to_datetime(out.index).tz_localize(None).normalize()
    out.index = out.index.map(lambda x: x.date())
    out = out.sort_index()
    return out


def trading_days_index(df: pd.DataFrame) -> List[date]:
    return list(df.index)


def next_trading_day_open(
    df: pd.DataFrame, signal_day: date
) -> Optional[Tuple[date, float]]:
    days = trading_days_index(df)
    for d in days:
        if d > signal_day:
            row = df.loc[d]
            o = float(row["Open"])
            return d, o
    return None


def exit_open_after_hold(
    df: pd.DataFrame, entry_day: date, exit_lag_sessions: int
) -> Optional[Tuple[date, float]]:
    """
    Exit at open of trading day index entry_idx + exit_lag_sessions
    (entry day = index 0; lag 5 => 6th trading day open after 5 held sessions).
    """
    days = trading_days_index(df)
    try:
        i0 = days.index(entry_day)
    except ValueError:
        return None
    exit_i = i0 + exit_lag_sessions
    if exit_i >= len(days):
        return None
    ed = days[exit_i]
    o = float(df.loc[ed]["Open"])
    return ed, o


def date_range_covering_signals(
    signal_dates: List[date], hold_lag: int = 5
) -> Tuple[date, date]:
    if not signal_dates:
        today = date.today()
        return today - timedelta(days=30), today
    lo = min(signal_dates)
    hi = max(signal_dates)
    start = lo - timedelta(days=7)
    end = hi + timedelta(days=40 + hold_lag * 7)
    return start, end
