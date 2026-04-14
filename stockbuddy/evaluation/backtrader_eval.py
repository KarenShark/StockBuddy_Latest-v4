"""
Layer-2 backtest via backtrader: MultiAgent-Signal vs Buy-and-Hold vs MACD(12,26,9).

Signal direction_score → target equity allocation:
  BUY(+2)=95%  OVERWEIGHT(+1)=70%  HOLD(0)=keep  UNDERWEIGHT(-1)=30%  SELL(-2)=0%
Commission: HK equity ~15.9 bps per side (stamp + SFC/FRC levy + exchange fee + broker).

All strategies share the same evaluation window (first signal date → last signal date + tail)
and the same trading frequency (weekly analysis dates) to ensure fair comparison.

Usage:
  python -m stockbuddy.evaluation.backtrader_eval --batch-dir <path>
  python -m stockbuddy.evaluation.backtrader_eval --decisions-jsonl <path> [--out <dir>]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple

import backtrader as bt
import numpy as np
import pandas as pd

from stockbuddy.evaluation.prices import fetch_ohlc, normalize_hk_symbol

# ── constants ────────────────────────────────────────────────────

# stamp_duty 0.1% + sfc 0.27bps + frc 0.15bps + exch 0.565bps + broker 5bps
HK_COMM = 0.001585
CASH0 = 100_000.0
ANN = 252
MACD_WARMUP_DAYS = 60  # calendar days before first signal for indicator warmup
EVAL_TAIL_DAYS = 10    # calendar days after last signal for position effect

# direction_score → target fraction of portfolio; None → hold current
TARGET_ALLOC: Dict[int, Optional[float]] = {
    2: 0.95,   # BUY
    1: 0.70,   # OVERWEIGHT
    0: None,   # HOLD — no rebalance
    -1: 0.30,  # UNDERWEIGHT
    -2: 0.0,   # SELL — all cash
}

_A2S = {"BUY": 2, "OVERWEIGHT": 1, "HOLD": 0, "UNDERWEIGHT": -1, "SELL": -2}


# ── data helpers ─────────────────────────────────────────────────


def _load_signals(path: Path) -> Tuple[str, Dict[date, int], Dict[str, int]]:
    """Parse decisions.jsonl → (ticker, {date→score}, action_counts)."""
    sigs: Dict[date, int] = {}
    ticker: Optional[str] = None
    cnt: Counter = Counter()
    with open(path, encoding="utf-8") as f:
        for raw in f:
            raw = raw.strip()
            if not raw:
                continue
            r = json.loads(raw)
            if ticker is None:
                ticker = r.get("ticker")
            ad = r.get("analysis_date")
            if not ad:
                continue
            ds = r.get("direction_score")
            act = (r.get("action") or "").strip().upper()
            score = int(ds) if ds is not None else _A2S.get(act)
            if score is None:
                continue
            sigs[datetime.strptime(ad.strip(), "%Y-%m-%d").date()] = score
            cnt[act] += 1
    if not ticker:
        raise ValueError("decisions.jsonl missing ticker")
    return str(ticker), sigs, dict(cnt)


def _make_feed(ohlc: pd.DataFrame) -> bt.feeds.PandasData:
    """Fresh backtrader PandasData feed from our OHLC DataFrame."""
    cols = [c for c in ("Open", "High", "Low", "Close", "Volume") if c in ohlc.columns]
    df = ohlc[cols].copy()
    df.index = pd.to_datetime(df.index)
    return bt.feeds.PandasData(
        dataname=df,
        open="Open", high="High", low="Low", close="Close",
        volume="Volume", openinterest=None,
    )


# ── analyzers ────────────────────────────────────────────────────


class _EqCurve(bt.Analyzer):
    """Record daily portfolio value (cash + position mark-to-market)."""

    def start(self):
        self.rows: List[Tuple[date, float]] = []

    def next(self):
        self.rows.append(
            (self.data.datetime.date(0), self.strategy.broker.getvalue())
        )

    def get_analysis(self):
        return self.rows


class _OrderCounter(bt.Analyzer):
    """Count submitted orders (more meaningful than round_trips for rebalancing)."""

    def start(self):
        self.count = 0

    def notify_order(self, order):
        if order.status == order.Completed:
            self.count += 1

    def get_analysis(self):
        return self.count


# ── strategies ───────────────────────────────────────────────────


class SignalStrategy(bt.Strategy):
    """Rebalance to target allocation on signal dates; hold otherwise.

    Orders execute at next bar open (backtrader default),
    simulating "signal at close → trade next open".
    """
    params = (("signals", {}), ("alloc", TARGET_ALLOC))

    def next(self):
        score = self.p.signals.get(self.data.datetime.date(0))
        if score is not None:
            tgt = self.p.alloc.get(score)
            if tgt is not None:
                self.order_target_percent(target=tgt)


class BuyAndHoldStrategy(bt.Strategy):
    """Full investment from first signal date, hold until end."""
    params = (("entry_date", None),)

    def next(self):
        if self.position:
            return
        today = self.data.datetime.date(0)
        if self.p.entry_date is not None and today < self.p.entry_date:
            return
        self.order_target_percent(target=0.95)


class MACDStrategy(bt.Strategy):
    """MACD(12,26,9) state-based, long-only, constrained to trade_dates only.

    On each trade_date: if MACD > signal → 95% long; if MACD ≤ signal → flat.
    Uses MACD *state* (not crossover event) so weekly sampling is meaningful.
    """
    params = (("fast", 12), ("slow", 26), ("sig", 9), ("trade_dates", frozenset()))

    def __init__(self):
        self.macd = bt.indicators.MACD(
            self.data.close,
            period_me1=self.p.fast,
            period_me2=self.p.slow,
            period_signal=self.p.sig,
        )

    def next(self):
        today = self.data.datetime.date(0)
        if self.p.trade_dates and today not in self.p.trade_dates:
            return
        bullish = self.macd.macd[0] > self.macd.signal[0]
        if bullish and not self.position:
            self.order_target_percent(target=0.95)
        elif not bullish and self.position:
            self.close()


# ── metrics from equity curve ────────────────────────────────────


def _trim_equity(
    eq: List[Tuple[date, float]],
    start: date,
    end: date,
) -> List[Tuple[date, float]]:
    """Keep only rows within [start, end]."""
    return [(d, v) for d, v in eq if start <= d <= end]


def _metrics(eq: List[Tuple[date, float]], cash0: float) -> Dict[str, Any]:
    if len(eq) < 2:
        return {"error": "insufficient_data"}
    v = np.array([x[1] for x in eq])
    d_list = [x[0] for x in eq]
    n = len(v)

    dr = np.diff(v) / v[:-1]
    tr = (v[-1] - cash0) / cash0
    af = ANN / n if n > 0 else 1.0
    ar = (1.0 + tr) ** af - 1.0

    s = float(np.std(dr, ddof=1)) if len(dr) > 1 else 0.0
    sharpe = round(float(np.mean(dr)) / s * np.sqrt(ANN), 4) if s > 1e-12 else None

    pk = np.maximum.accumulate(v)
    mdd = float(np.max((pk - v) / np.where(pk > 0, pk, 1.0)))
    calmar = round(ar / mdd, 4) if mdd > 1e-9 else None

    return {
        "final_value": round(float(v[-1]), 2),
        "total_return_pct": round(tr * 100, 4),
        "ann_return_pct": round(ar * 100, 4),
        "sharpe": sharpe,
        "max_dd_pct": round(mdd * 100, 4),
        "calmar": calmar,
        "n_days": n,
        "period": f"{d_list[0]}..{d_list[-1]}",
    }


def _trade_stats(ta, order_count: int) -> Dict[str, Any]:
    """Extract round-trip stats + order count."""
    def _g(obj, *keys):
        for k in keys:
            try:
                obj = getattr(obj, k) if hasattr(obj, k) else obj[k]
            except (KeyError, TypeError, IndexError, AttributeError):
                return 0
        return int(obj) if obj else 0

    closed = _g(ta, "total", "closed")
    won = _g(ta, "won", "total")
    lost = _g(ta, "lost", "total")
    return {
        "order_count": order_count,
        "round_trips": closed,
        "won": won,
        "lost": lost,
        "win_rate_pct": round(won / closed * 100, 2) if closed else None,
    }


# ── single strategy runner ───────────────────────────────────────


def _run_one(
    cls,
    ohlc: pd.DataFrame,
    cash: float,
    comm: float,
    *,
    eval_start: Optional[date] = None,
    eval_end: Optional[date] = None,
    **strategy_kwargs,
) -> Tuple[Dict[str, Any], List[Tuple[date, float]]]:
    cerebro = bt.Cerebro(stdstats=False)
    cerebro.addstrategy(cls, **strategy_kwargs)
    cerebro.adddata(_make_feed(ohlc))
    cerebro.broker.setcash(cash)
    cerebro.broker.setcommission(commission=comm)
    cerebro.addanalyzer(_EqCurve, _name="eq")
    cerebro.addanalyzer(_OrderCounter, _name="oc")
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="ta")

    results = cerebro.run()
    strat = results[0]

    eq_full = strat.analyzers.eq.get_analysis()
    oc = strat.analyzers.oc.get_analysis()
    ta = strat.analyzers.ta.get_analysis()

    # trim equity curve to evaluation window
    if eval_start and eval_end and eq_full:
        eq = _trim_equity(eq_full, eval_start, eval_end)
    else:
        eq = eq_full

    m = _metrics(eq, cash)
    m.update(_trade_stats(ta, oc))
    return m, eq


# ── main entry ───────────────────────────────────────────────────


def run_backtest(
    *,
    decisions_jsonl: Optional[Path] = None,
    batch_dir: Optional[Path] = None,
    initial_cash: float = CASH0,
    commission: float = HK_COMM,
    output_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Run Signal / B&H / MACD backtests; return JSON report."""
    if decisions_jsonl is not None:
        jp = Path(decisions_jsonl)
    elif batch_dir is not None:
        jp = Path(batch_dir) / "decisions.jsonl"
    else:
        raise ValueError("Provide decisions_jsonl or batch_dir")

    ticker, sigs, sig_dist = _load_signals(jp)
    symbol = normalize_hk_symbol(ticker)
    sd = sorted(sigs)
    if not sd:
        raise ValueError("No valid signals in decisions.jsonl")

    first_sig = sd[0]
    last_sig = sd[-1]
    trade_dates: FrozenSet[date] = frozenset(sd)

    # OHLC: warmup buffer before first signal + tail after last signal
    ohlc_start = first_sig - timedelta(days=MACD_WARMUP_DAYS)
    ohlc_end = last_sig + timedelta(days=EVAL_TAIL_DAYS + 15)
    ohlc = fetch_ohlc(symbol, ohlc_start, ohlc_end)
    if ohlc.empty:
        raise RuntimeError(f"No OHLC data for {symbol}")

    # evaluation window: first signal date → last signal date + EVAL_TAIL_DAYS
    eval_end_target = last_sig + timedelta(days=EVAL_TAIL_DAYS)
    ohlc_dates = sorted(d.date() for d in pd.to_datetime(ohlc.index))
    eval_end = max(d for d in ohlc_dates if d <= eval_end_target) if ohlc_dates else eval_end_target

    print(
        f"  [{symbol}] OHLC: {len(ohlc)} bars, signals: {len(sigs)}, "
        f"eval: {first_sig}..{eval_end}",
        flush=True,
    )

    sig_m, sig_eq = _run_one(
        SignalStrategy, ohlc, initial_cash, commission,
        eval_start=first_sig, eval_end=eval_end,
        signals=sigs,
    )
    bh_m, bh_eq = _run_one(
        BuyAndHoldStrategy, ohlc, initial_cash, commission,
        eval_start=first_sig, eval_end=eval_end,
        entry_date=first_sig,
    )
    macd_m, macd_eq = _run_one(
        MACDStrategy, ohlc, initial_cash, commission,
        eval_start=first_sig, eval_end=eval_end,
        trade_dates=trade_dates,
    )

    report: Dict[str, Any] = {
        "schema": "backtrader_eval_v2",
        "ts": datetime.now(timezone.utc).isoformat(),
        "symbol": symbol,
        "ticker": ticker,
        "n_signals": len(sigs),
        "signal_dist": sig_dist,
        "signal_range": f"{first_sig}..{last_sig}",
        "eval_window": f"{first_sig}..{eval_end}",
        "initial_cash": initial_cash,
        "commission_bps": round(commission * 10000, 1),
        "alloc_map": {str(k): v for k, v in TARGET_ALLOC.items()},
        "strategies": {
            "multi_agent": sig_m,
            "buy_and_hold": bh_m,
            "macd_12_26_9": macd_m,
        },
        "excess_vs_bh_pct": round(
            (sig_m.get("total_return_pct") or 0) - (bh_m.get("total_return_pct") or 0), 4
        ),
        "excess_vs_macd_pct": round(
            (sig_m.get("total_return_pct") or 0) - (macd_m.get("total_return_pct") or 0), 4
        ),
        "methodology": {
            "signal_rebalance": "order_target_percent on signal dates; HOLD=no_change",
            "buy_and_hold": "95% equity from first signal date, hold to end",
            "macd": "MACD(12,26,9) crossover; long-only; trades only on signal dates (weekly-aligned)",
            "execution": "market order filled at next bar open (no cheat-on-close)",
            "eval_window": f"first_signal..last_signal+{EVAL_TAIL_DAYS}cal_days",
            "entry_alignment": "all strategies can first trade on first signal date",
            "frequency_alignment": "MACD restricted to same weekly analysis dates as multi-agent",
            "commission_note": f"{commission*10000:.1f} bps per side (HK equity fee snapshot)",
            "fractional_shares": True,
            "prices": "yfinance daily OHLCV",
        },
    }

    # persist
    out = Path(output_dir) if output_dir else jp.parent / "backtest_bt"
    out.mkdir(parents=True, exist_ok=True)

    (out / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    for name, eq in [("signal", sig_eq), ("buy_hold", bh_eq), ("macd", macd_eq)]:
        pd.DataFrame(eq, columns=["date", "value"]).to_csv(
            out / f"equity_{name}.csv", index=False,
        )

    report["output_dir"] = str(out)
    return report


# ── CLI ──────────────────────────────────────────────────────────


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Layer-2 backtrader backtest")
    p.add_argument("--batch-dir", type=Path)
    p.add_argument("--decisions-jsonl", type=Path)
    p.add_argument("--out", type=Path, help="Output directory")
    p.add_argument("--cash", type=float, default=CASH0)
    a = p.parse_args(argv)

    r = run_backtest(
        decisions_jsonl=a.decisions_jsonl, batch_dir=a.batch_dir,
        initial_cash=a.cash, output_dir=a.out,
    )
    strats = r["strategies"]
    header = f"{'Strategy':<20} {'Return%':>10} {'Sharpe':>8} {'MDD%':>8} {'Orders':>7}"
    print(f"\n{header}")
    print("-" * len(header))
    for name, m in strats.items():
        ret = m.get("total_return_pct", "?")
        sh = m.get("sharpe") or "–"
        dd = m.get("max_dd_pct", "?")
        oc = m.get("order_count", "?")
        print(f"{name:<20} {ret!s:>10} {sh!s:>8} {dd!s:>8} {oc!s:>7}")

    print(f"\nEval window: {r.get('eval_window')}")
    print(f"Excess vs B&H: {r.get('excess_vs_bh_pct')}%")
    print(f"Excess vs MACD: {r.get('excess_vs_macd_pct')}%")
    print(f"Output: {r.get('output_dir')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
