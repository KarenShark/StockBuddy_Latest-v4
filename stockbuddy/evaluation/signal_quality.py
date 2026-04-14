"""
Signal quality evaluation: Spearman IC, Hit Rate, Long-Short spread.

All key metrics include bootstrap 95% CI and p-values.
Horizons: 1d, 5d, 10d, 20d forward close-to-close returns.
Supports per-stock and pooled (multi-stock) analysis.

Usage:
    python -m stockbuddy.evaluation.signal_quality --batch-dir <path>
    python -m stockbuddy.evaluation.signal_quality --decisions-jsonl <path>
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats

from stockbuddy.evaluation.prices import (
    date_range_covering_signals,
    fetch_ohlc,
    normalize_hk_symbol,
    trading_days_index,
)

# ── direction mapping ────────────────────────────────────────────
# Ordinal -2..+2 for five-way actions; Spearman IC uses this scale.

ACTION_DIRECTION = {
    "SELL": -2,
    "UNDERWEIGHT": -1,
    "HOLD": 0,
    "OVERWEIGHT": 1,
    "BUY": 2,
}
DEFAULT_HORIZONS = (1, 5, 10, 20)
_ACTION_ORDER = ("SELL", "UNDERWEIGHT", "HOLD", "OVERWEIGHT", "BUY")
N_BOOTSTRAP = 2000
BOOTSTRAP_SEED = 42


# ── data loading ─────────────────────────────────────────────────


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _parse_action(a: Any) -> Optional[str]:
    if a is None:
        return None
    t = str(a).strip().upper()
    return t if t in ACTION_DIRECTION else None


@dataclass
class SignalRow:
    analysis_date: date
    ticker: str
    action: str  # BUY | OVERWEIGHT | HOLD | UNDERWEIGHT | SELL
    action_pre_gate: Optional[str]
    direction: int  # -2..+2 ordinal
    direction_pre_gate: Optional[int]
    news_status: Optional[str]
    confidence: Optional[float]
    fwd_returns: Dict[int, Optional[float]] = field(default_factory=dict)


# ── forward returns ──────────────────────────────────────────────


def _close_on_or_before(ohlc: pd.DataFrame, d: date) -> Optional[float]:
    """Close price on date d, or the most recent trading day before d."""
    days = trading_days_index(ohlc)
    if d in ohlc.index:
        return float(ohlc.loc[d]["Close"])
    for td in reversed(days):
        if td <= d:
            return float(ohlc.loc[td]["Close"])
    return None


def _close_n_days_after(
    ohlc: pd.DataFrame, ref_day: date, n_sessions: int
) -> Optional[Tuple[date, float]]:
    """Close price n trading sessions after ref_day."""
    days = trading_days_index(ohlc)
    try:
        i0 = days.index(ref_day)
    except ValueError:
        for i, d in enumerate(days):
            if d >= ref_day:
                i0 = i
                break
        else:
            return None
    target_i = i0 + n_sessions
    if target_i >= len(days):
        return None
    td = days[target_i]
    return td, float(ohlc.loc[td]["Close"])


def _compute_forward_returns(
    ohlc: pd.DataFrame,
    sig_date: date,
    horizons: Tuple[int, ...],
) -> Dict[int, Optional[float]]:
    """Close-to-close forward returns: close(D) → close(D+h)."""
    ref_close = _close_on_or_before(ohlc, sig_date)
    if ref_close is None or ref_close <= 0:
        return {h: None for h in horizons}
    result: Dict[int, Optional[float]] = {}
    for h in horizons:
        fwd = _close_n_days_after(ohlc, sig_date, h)
        if fwd is None:
            result[h] = None
        else:
            result[h] = (fwd[1] - ref_close) / ref_close
    return result


# ── statistical helpers ──────────────────────────────────────────


def _spearman_ic(
    directions: np.ndarray, returns: np.ndarray
) -> Tuple[float, float]:
    """Spearman rank correlation + two-sided p-value.
    Returns (nan, nan) if fewer than 3 valid pairs or zero variance."""
    mask = np.isfinite(returns) & np.isfinite(directions)
    d, r = directions[mask], returns[mask]
    if len(d) < 3:
        return float("nan"), float("nan")
    if np.std(d) == 0 or np.std(r) == 0:
        return float("nan"), float("nan")
    rho, p = stats.spearmanr(d, r)
    return float(rho), float(p)


def _bootstrap_ci(
    values: np.ndarray,
    stat_fn,
    n_boot: int = N_BOOTSTRAP,
    ci: float = 0.95,
    seed: int = BOOTSTRAP_SEED,
) -> Tuple[float, float, float]:
    """Bootstrap confidence interval. Returns (point_estimate, ci_low, ci_high)."""
    rng = np.random.default_rng(seed)
    n = len(values)
    if n < 2:
        return float("nan"), float("nan"), float("nan")
    point = stat_fn(values)
    boot_stats = np.empty(n_boot)
    for i in range(n_boot):
        sample = rng.choice(values, size=n, replace=True)
        boot_stats[i] = stat_fn(sample)
    alpha = (1 - ci) / 2
    lo = float(np.nanpercentile(boot_stats, alpha * 100))
    hi = float(np.nanpercentile(boot_stats, (1 - alpha) * 100))
    return float(point), lo, hi


def _bootstrap_ic_ci(
    directions: np.ndarray,
    returns: np.ndarray,
    n_boot: int = N_BOOTSTRAP,
    ci: float = 0.95,
    seed: int = BOOTSTRAP_SEED,
) -> Tuple[float, float, float]:
    """Bootstrap CI specifically for Spearman IC (paired resampling)."""
    mask = np.isfinite(returns) & np.isfinite(directions)
    d, r = directions[mask], returns[mask]
    n = len(d)
    if n < 5:
        return float("nan"), float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    point, _ = _spearman_ic(d, r)
    boot_ics = np.empty(n_boot)
    for i in range(n_boot):
        idx = rng.choice(n, size=n, replace=True)
        ic_val, _ = _spearman_ic(d[idx], r[idx])
        boot_ics[i] = ic_val
    valid = boot_ics[np.isfinite(boot_ics)]
    if len(valid) < n_boot * 0.5:
        return point, float("nan"), float("nan")
    alpha = (1 - ci) / 2
    lo = float(np.nanpercentile(valid, alpha * 100))
    hi = float(np.nanpercentile(valid, (1 - alpha) * 100))
    return point, lo, hi


def _hit_rate_with_test(
    directions: np.ndarray, returns: np.ndarray, target_dir: int
) -> Dict[str, Any]:
    """Hit rate for bullish bucket (direction>=1) or bearish (direction<=-1)."""
    if target_dir >= 1:
        mask = (directions >= 1) & np.isfinite(returns)
        rets = returns[mask]
        n = len(rets)
        if n == 0:
            return {"n": 0, "hit_rate": None, "p_value": None}
        hits = int(np.sum(rets > 0))
    else:
        mask = (directions <= -1) & np.isfinite(returns)
        rets = returns[mask]
        n = len(rets)
        if n == 0:
            return {"n": 0, "hit_rate": None, "p_value": None}
        hits = int(np.sum(rets < 0))
    hr = hits / n
    # H0: hit_rate = 0.5 (random)
    bt = stats.binomtest(hits, n, 0.5, alternative="greater")
    return {
        "n": n,
        "hits": hits,
        "hit_rate": round(hr, 4),
        "p_value": round(bt.pvalue, 6),
        "significant_at_10pct": bool(bt.pvalue < 0.10),
        "significant_at_5pct": bool(bt.pvalue < 0.05),
    }


def _long_short_spread(
    directions: np.ndarray, returns: np.ndarray
) -> Dict[str, Any]:
    """Mean return when bullish (direction>=1) vs bearish (direction<=-1)."""
    mask_fin = np.isfinite(returns)
    long_r = returns[(directions >= 1) & mask_fin]
    short_r = returns[(directions <= -1) & mask_fin]
    result: Dict[str, Any] = {
        "n_long": len(long_r),
        "n_short": len(short_r),
    }
    if len(long_r) > 0:
        result["mean_return_long"] = round(float(np.mean(long_r)), 6)
    if len(short_r) > 0:
        result["mean_return_short"] = round(float(np.mean(short_r)), 6)
    if len(long_r) >= 2 and len(short_r) >= 2:
        spread = float(np.mean(long_r) - np.mean(short_r))
        t_stat, p_val = stats.ttest_ind(long_r, short_r, equal_var=False)
        result["spread"] = round(spread, 6)
        result["t_stat"] = round(float(t_stat), 4)
        result["p_value"] = round(float(p_val), 6)
        result["significant_at_10pct"] = bool(p_val < 0.10)
        result["significant_at_5pct"] = bool(p_val < 0.05)
    else:
        result["spread"] = None
        result["note"] = "insufficient_samples_for_t_test"
    return result


# ── signal distribution ──────────────────────────────────────────


def _signal_distribution(
    rows: List[SignalRow], *, cross_section: bool = False
) -> Dict[str, Any]:
    cnt = Counter(r.action for r in rows)
    n = len(rows)
    dist = {a: cnt.get(a, 0) for a in _ACTION_ORDER}
    ratios = {f"{a}_ratio": round(dist[a] / n, 4) if n else 0.0 for a in dist}

    # Shannon entropy (base 2)
    probs = [dist[a] / n for a in dist if dist[a] > 0]
    entropy = -sum(p * math.log2(p) for p in probs) if probs else 0.0

    # consecutive-row turnover meaningless when rows mix tickers / dates interleaved
    turnover: Optional[float]
    if cross_section or n < 2:
        turnover = None
    else:
        changes = sum(
            1 for i in range(1, n) if rows[i].action != rows[i - 1].action
        )
        turnover = round(changes / (n - 1), 4)

    max_share = max(dist.values()) / n if n else 0.0
    return {
        "n_signals": n,
        "counts": dist,
        **ratios,
        "entropy_bits": round(entropy, 4),
        "max_entropy_bits": round(math.log2(5), 4),
        "signal_turnover": turnover,
        "degenerate": max_share > 0.85 if n else False,
    }


def _news_diagnostic(rows: List[SignalRow]) -> Dict[str, Any]:
    cnt = Counter(r.news_status for r in rows)
    n = len(rows)
    ok_n = cnt.get("ok", 0)
    return {
        "n_signals": n,
        "status_counts": dict(cnt),
        "news_ok_rate": round(ok_n / n, 4) if n else 0.0,
        "news_ok_threshold_met": (ok_n / n >= 0.8) if n else False,
    }


# ── per-horizon evaluation ───────────────────────────────────────


def _evaluate_horizon(
    rows: List[SignalRow], horizon: int, use_pre_gate: bool = False
) -> Dict[str, Any]:
    """Full evaluation for one forward return horizon."""
    dirs = []
    rets = []
    for r in rows:
        d = r.direction_pre_gate if use_pre_gate else r.direction
        if d is None:
            continue
        fwd = r.fwd_returns.get(horizon)
        dirs.append(d)
        rets.append(fwd if fwd is not None else float("nan"))

    directions = np.array(dirs, dtype=float)
    returns = np.array(rets, dtype=float)

    valid_mask = np.isfinite(returns) & np.isfinite(directions)
    n_valid = int(np.sum(valid_mask))

    # IC
    ic_val, ic_p = _spearman_ic(directions, returns)
    ic_point, ic_lo, ic_hi = _bootstrap_ic_ci(directions, returns)

    # Hit rates (bullish = score>=1, bearish = score<=-1)
    buy_hr = _hit_rate_with_test(directions, returns, target_dir=1)
    sell_hr = _hit_rate_with_test(directions, returns, target_dir=-1)
    # overall directional: long bucket → positive OR short bucket → negative (HOLD excluded)
    non_hold = valid_mask & (directions != 0)
    if np.sum(non_hold) > 0:
        d_nh = directions[non_hold]
        r_nh = returns[non_hold]
        correct = int(
            np.sum((d_nh > 0) & (r_nh > 0)) + np.sum((d_nh < 0) & (r_nh < 0))
        )
        overall_hr = correct / len(d_nh)
        overall_bt = stats.binomtest(correct, len(d_nh), 0.5, alternative="greater")
        overall_p = float(overall_bt.pvalue)
    else:
        overall_hr = None
        overall_p = None

    # Long-Short
    ls = _long_short_spread(directions, returns)

    return {
        "horizon_days": horizon,
        "n_valid_pairs": n_valid,
        "ic": {
            "spearman_rho": _r4(ic_val),
            "p_value": _r6(ic_p),
            "bootstrap_95ci": [_r4(ic_lo), _r4(ic_hi)],
            "significant_at_10pct": bool(ic_p < 0.10) if not math.isnan(ic_p) else None,
            "significant_at_5pct": bool(ic_p < 0.05) if not math.isnan(ic_p) else None,
        },
        "hit_rate": {
            "buy": buy_hr,
            "sell": sell_hr,
            "overall_directional": {
                "rate": _r4(overall_hr) if overall_hr is not None else None,
                "p_value": _r6(overall_p) if overall_p is not None else None,
            },
        },
        "long_short": ls,
    }


def _r4(v):
    return round(v, 4) if v is not None and not math.isnan(v) else None

def _r6(v):
    return round(v, 6) if v is not None and not math.isnan(v) else None


# ── main entry ───────────────────────────────────────────────────


def evaluate_signal_quality(
    *,
    decisions_jsonl: Path | None = None,
    batch_dir: Path | None = None,
    horizons: Tuple[int, ...] = DEFAULT_HORIZONS,
) -> Dict[str, Any]:
    """Evaluate signal quality from decisions.jsonl.

    Returns a JSON-serializable dict with:
      - signal_distribution
      - news_diagnostic
      - per_horizon (post-gate)
      - per_horizon_pre_gate
      - go_no_go (pilot diagnostics)
      - per_signal (detailed per-row data for further analysis)
    """
    if decisions_jsonl is not None:
        jsonl_path = Path(decisions_jsonl)
    elif batch_dir is not None:
        jsonl_path = Path(batch_dir) / "decisions.jsonl"
    else:
        raise ValueError("Provide batch_dir or decisions_jsonl")

    if not jsonl_path.is_file():
        raise FileNotFoundError(jsonl_path)

    raw_rows = _load_jsonl(jsonl_path)
    if not raw_rows:
        raise ValueError("decisions.jsonl is empty")

    # Parse rows; each row carries its own ticker (single- or multi-stock jsonl)
    rows: List[SignalRow] = []
    for raw in raw_rows:
        act = _parse_action(raw.get("action"))
        if act is None:
            continue
        pre = _parse_action(raw.get("parsed_action_pre_gate"))
        ad_str = raw.get("analysis_date")
        if not ad_str:
            continue
        tk = str(raw.get("ticker") or "").strip()
        if not tk:
            continue
        ad = datetime.strptime(ad_str.strip(), "%Y-%m-%d").date()
        rows.append(
            SignalRow(
                analysis_date=ad,
                ticker=tk,
                action=act,
                action_pre_gate=pre,
                direction=ACTION_DIRECTION[act],
                direction_pre_gate=ACTION_DIRECTION.get(pre) if pre else None,
                news_status=raw.get("news_status"),
                confidence=raw.get("confidence"),
            )
        )

    rows.sort(key=lambda r: (r.analysis_date, r.ticker))

    if len(rows) < 3:
        raise ValueError(f"Only {len(rows)} valid signals; need >= 3 for IC")

    tickers_u = sorted({r.ticker for r in rows})
    cross_section = len(tickers_u) > 1
    max_h = max(horizons)

    by_tk: Dict[str, List[SignalRow]] = {}
    for r in rows:
        by_tk.setdefault(r.ticker, []).append(r)

    for tk, trows in by_tk.items():
        symbol = normalize_hk_symbol(tk)
        sig_dates = [r.analysis_date for r in trows]
        start_d = min(sig_dates) - timedelta(days=7)
        end_d = max(sig_dates) + timedelta(days=max_h * 2 + 14)
        ohlc = fetch_ohlc(symbol, start_d, end_d)
        if ohlc.empty:
            raise RuntimeError(f"No OHLC data for {tk} ({symbol})")
        for r in trows:
            r.fwd_returns = _compute_forward_returns(
                ohlc, r.analysis_date, horizons
            )

    dist = _signal_distribution(rows, cross_section=cross_section)

    # News diagnostic
    news_diag = _news_diagnostic(rows)

    # Per-horizon evaluation (post-gate and pre-gate)
    post_gate = {h: _evaluate_horizon(rows, h, use_pre_gate=False) for h in horizons}
    pre_gate = {h: _evaluate_horizon(rows, h, use_pre_gate=True) for h in horizons}

    # Gate impact analysis
    gate_changes = sum(
        1 for r in rows
        if r.action_pre_gate is not None and r.action_pre_gate != r.action
    )

    # Go/No-Go summary (pilot diagnostics)
    ref_h = 5  # primary horizon for go/no-go
    ref_eval = post_gate.get(ref_h, {})
    ref_ic = ref_eval.get("ic", {}).get("spearman_rho")
    ref_ic_p = ref_eval.get("ic", {}).get("p_value")
    ref_buy_hr = (ref_eval.get("hit_rate", {}).get("buy", {}) or {}).get("hit_rate")

    go_no_go = {
        "primary_horizon": ref_h,
        "check_1_signal_distribution": {
            "pass": not dist["degenerate"],
            "detail": dist["counts"],
        },
        "check_2_news_availability": {
            "pass": news_diag["news_ok_threshold_met"],
            "news_ok_rate": news_diag["news_ok_rate"],
        },
        "check_3_ic_positive": {
            "pass": ref_ic is not None and ref_ic > 0,
            "ic": ref_ic,
            "p_value": ref_ic_p,
            "strong_pass": (
                ref_ic is not None
                and ref_ic > 0.05
                and ref_ic_p is not None
                and ref_ic_p < 0.10
            ),
        },
        "check_4_hit_rate": {
            "pass": ref_buy_hr is not None and ref_buy_hr > 0.50,
            "buy_hit_rate": ref_buy_hr,
        },
    }
    all_pass = all(
        go_no_go[k]["pass"] for k in go_no_go if k != "primary_horizon"
    )
    go_no_go["overall"] = "GO" if all_pass else "REVIEW"

    # Per-signal detail (for downstream analysis / plots)
    per_signal = []
    for r in rows:
        per_signal.append({
            "analysis_date": r.analysis_date.isoformat(),
            "ticker": r.ticker,
            "action": r.action,
            "action_pre_gate": r.action_pre_gate,
            "direction": r.direction,
            "news_status": r.news_status,
            "confidence": r.confidence,
            "fwd_returns": {str(k): _r6(v) for k, v in r.fwd_returns.items()},
        })

    if len(tickers_u) == 1:
        sym_out = normalize_hk_symbol(tickers_u[0])
        ticker_out = tickers_u[0]
    else:
        sym_out = "multi"
        ticker_out = "pooled"

    report = {
        "schema": "signal_quality_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "symbol": sym_out,
        "ticker": ticker_out,
        "n_signals": len(rows),
        "date_range": f"{rows[0].analysis_date.isoformat()}..{rows[-1].analysis_date.isoformat()}",
        "horizons_evaluated": list(horizons),
        "signal_distribution": dist,
        "news_diagnostic": news_diag,
        "per_horizon_post_gate": {str(h): v for h, v in post_gate.items()},
        "per_horizon_pre_gate": {str(h): v for h, v in pre_gate.items()},
        "risk_gate_impact": {
            "signals_changed_by_gate": gate_changes,
            "gate_change_rate": round(gate_changes / len(rows), 4),
        },
        "go_no_go": go_no_go,
        "per_signal": per_signal,
        "methodology": {
            "ic_method": "spearman_rank_correlation",
            "direction_scale": "ordinal_-2_to_+2 (SELL,UNDERWEIGHT,HOLD,OVERWEIGHT,BUY)",
            "forward_return": "close_to_close",
            "hit_rate_test": "binomial_test_H0_p=0.5",
            "hit_rate_bullish": "direction>=1 vs fwd_return>0",
            "hit_rate_bearish": "direction<=-1 vs fwd_return<0",
            "long_short_test": "welch_t_test",
            "long_short_buckets": "long: direction>=1, short: direction<=-1",
            "bootstrap_samples": N_BOOTSTRAP,
            "bootstrap_ci": "95%",
            "bootstrap_seed": BOOTSTRAP_SEED,
        },
    }
    if cross_section:
        report["mode"] = "pooled"
        report["universe"] = tickers_u
        report["n_per_ticker"] = {tk: len(by_tk[tk]) for tk in tickers_u}

    return report


# ── CLI ──────────────────────────────────────────────────────────


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(
        description="Signal quality evaluation (IC, Hit Rate, Long-Short)"
    )
    p.add_argument("--batch-dir", type=Path, help="Batch directory with decisions.jsonl")
    p.add_argument("--decisions-jsonl", type=Path, help="Direct path to decisions.jsonl")
    p.add_argument(
        "--horizons",
        type=str,
        default="1,5,10,20",
        help="Comma-separated forward return horizons in trading days",
    )
    p.add_argument("--out", type=Path, help="Output JSON path (default: stdout)")
    args = p.parse_args(argv)

    horizons = tuple(int(x.strip()) for x in args.horizons.split(","))

    report = evaluate_signal_quality(
        batch_dir=args.batch_dir,
        decisions_jsonl=args.decisions_jsonl,
        horizons=horizons,
    )

    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"Written to {args.out}")
    else:
        print(text)

    # Print summary to stderr for quick check
    go = report["go_no_go"]
    print(f"\n{'='*50}", file=sys.stderr)
    print(f"Signal Quality: {go['overall']}", file=sys.stderr)
    for k, v in go.items():
        if k in ("primary_horizon", "overall"):
            continue
        status = "PASS" if v.get("pass") else "FAIL"
        print(f"  {k}: {status}", file=sys.stderr)
    h5 = report["per_horizon_post_gate"].get("5", {})
    ic_info = h5.get("ic", {})
    print(
        f"  5d IC = {ic_info.get('spearman_rho')} "
        f"(p={ic_info.get('p_value')}, "
        f"95%CI={ic_info.get('bootstrap_95ci')})",
        file=sys.stderr,
    )
    print(f"{'='*50}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
