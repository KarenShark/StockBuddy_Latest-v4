"""
Formal evaluation v2 — frozen protocol, 6-month window, 10-ticker universe.

Period  : 2024-03-01 ~ 2024-08-31 (6 calendar months)
Universe: 10 high-liquidity HK stocks, 8 sectors (see FORMAL_EVAL_V2_TICKERS)
Profiles: buy_and_hold / single_agent / full_system  (same as v1)
Calendar: monthly first HK session, proxy 0700.HK

Total cells: 10 tickers × 3 profiles = 30 parallel jobs, each runs 6 dates.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
import uuid
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from stockbuddy.experiments.timeline import PilotTimelineResult

from pathlib import Path

from stockbuddy.default_config import DEFAULT_CONFIG
from stockbuddy.evaluation.prices import (
    fetch_ohlc,
    normalize_hk_symbol,
    trading_days_index,
)

FORMAL_EVAL_V2_VERSION = "v2"

# fmt: off
# 10 tickers, 8 sectors — chosen for high HK liquidity and sector diversity.
# Sector tags are for human reference; not used in code.
FORMAL_EVAL_V2_TICKERS: List[str] = [
    "0700",  # Tencent           — Tech / Internet
    "9988",  # Alibaba HK        — E-commerce
    "0005",  # HSBC              — Banking
    "1299",  # AIA Group         — Insurance
    "0941",  # China Mobile      — Telecom
    "0388",  # HKEX              — Financial Exchange
    "0883",  # CNOOC             — Energy / Oil
    "0016",  # Sun Hung Kai Prop — Real Estate
    "1211",  # BYD               — Auto / EV
    "2020",  # ANTA Sports       — Consumer / Sportswear
]
# fmt: on

FORMAL_EVAL_V2_PERIOD_START = "2024-03-01"
FORMAL_EVAL_V2_PERIOD_END = "2024-08-31"

# First HK session per calendar month, 0700.HK calendar; verified 2026-03-28.
FORMAL_EVAL_V2_ANALYSIS_DATES_ISO: List[str] = [
    "2024-03-01",
    "2024-04-02",
    "2024-05-02",
    "2024-06-03",
    "2024-07-02",
    "2024-08-01",
]

FORMAL_EVAL_V2_ANALYSTS: List[str] = ["market", "fundamentals"]

FORMAL_EVAL_V2_PROFILES: Tuple[str, ...] = (
    "buy_and_hold",
    "single_agent",
    "full_system",
)

_PROFILE_ORDER: Dict[str, int] = {p: i for i, p in enumerate(FORMAL_EVAL_V2_PROFILES)}
_TICKER_ORDER: Dict[str, int] = {t: i for i, t in enumerate(FORMAL_EVAL_V2_TICKERS)}

# Default worker cap; override with FORMAL_EVAL_V2_WORKERS env var.
_DEFAULT_WORKERS = 5


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _load_project_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(_repo_root() / ".env")


def _parallel_workers(task_count: int, override: Optional[int] = None) -> int:
    if task_count < 1:
        return 1
    if override is not None:
        return max(1, min(int(override), task_count))
    raw = os.getenv("FORMAL_EVAL_V2_WORKERS", "").strip()
    if raw:
        return max(1, min(int(raw), task_count))
    return max(1, min(_DEFAULT_WORKERS, task_count))


def _period_dates() -> Tuple[date, date]:
    a = FORMAL_EVAL_V2_PERIOD_START.split("-")
    b = FORMAL_EVAL_V2_PERIOD_END.split("-")
    return (
        date(int(a[0]), int(a[1]), int(a[2])),
        date(int(b[0]), int(b[1]), int(b[2])),
    )


def _year_months_in_period(lo: date, hi: date) -> List[Tuple[int, int]]:
    out: List[Tuple[int, int]] = []
    y, m = lo.year, lo.month
    while (y, m) <= (hi.year, hi.month):
        out.append((y, m))
        m = m + 1 if m < 12 else 1
        if m == 1:
            y += 1
    return out


def compute_monthly_first_trading_days() -> List[str]:
    """Recompute from 0700.HK; result must match FORMAL_EVAL_V2_ANALYSIS_DATES_ISO."""
    lo, hi = _period_dates()
    sym = normalize_hk_symbol("0700")
    df = fetch_ohlc(sym, lo, hi)
    days = trading_days_index(df)
    out: List[str] = []
    for y, month in _year_months_in_period(lo, hi):
        first: Optional[date] = next(
            (d for d in days if d.year == y and d.month == month), None
        )
        if first is None:
            raise RuntimeError(f"no HK session in {y}-{month:02d} for proxy 0700.HK")
        out.append(first.isoformat())
    return out


def assert_frozen_dates_match_calendar() -> None:
    got = compute_monthly_first_trading_days()
    if got != FORMAL_EVAL_V2_ANALYSIS_DATES_ISO:
        raise AssertionError(
            f"FORMAL_EVAL_V2_ANALYSIS_DATES_ISO out of sync: "
            f"frozen={FORMAL_EVAL_V2_ANALYSIS_DATES_ISO} live={got}"
        )


def formal_eval_v2_snapshot() -> Dict[str, Any]:
    return {
        "version": FORMAL_EVAL_V2_VERSION,
        "tickers": list(FORMAL_EVAL_V2_TICKERS),
        "period_start": FORMAL_EVAL_V2_PERIOD_START,
        "period_end": FORMAL_EVAL_V2_PERIOD_END,
        "analysis_dates": list(FORMAL_EVAL_V2_ANALYSIS_DATES_ISO),
        "selected_analysts": list(FORMAL_EVAL_V2_ANALYSTS),
        "profiles": list(FORMAL_EVAL_V2_PROFILES),
        "absolute_no_news": True,
        "memory_disabled": True,
        "calendar_proxy": "0700.HK",
        "n_analysis_dates": len(FORMAL_EVAL_V2_ANALYSIS_DATES_ISO),
        "n_tickers": len(FORMAL_EVAL_V2_TICKERS),
        "fee_schedule": DEFAULT_CONFIG.get("backtest_fee_schedule") or {},
        "sector_map": {
            "0700": "Tech/Internet",
            "9988": "E-commerce",
            "0005": "Banking",
            "1299": "Insurance",
            "0941": "Telecom",
            "0388": "Financial Exchange",
            "0883": "Energy/Oil",
            "0016": "Real Estate",
            "1211": "Auto/EV",
            "2020": "Consumer/Sportswear",
        },
    }


def formal_eval_v2_merged_config(extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Same config dict for every ticker × profile cell."""
    base: Dict[str, Any] = {
        **DEFAULT_CONFIG,
        "memory_enabled": False,
        "formal_eval_v2": True,
        "formal_eval_v2_snapshot": formal_eval_v2_snapshot(),
    }
    if os.getenv("DEEP_THINK_LLM"):
        base["deep_think_llm"] = os.environ["DEEP_THINK_LLM"]
    if os.getenv("QUICK_THINK_LLM"):
        base["quick_think_llm"] = os.environ["QUICK_THINK_LLM"]
    if extra:
        base.update(extra)
    return base


def _grid_worker(
    ticker: str,
    profile: str,
    dates: List[str],
    cfg: Dict[str, Any],
    bid: str,
) -> Dict[str, Any]:
    from stockbuddy.evaluation.timeline_backtest import run_timeline_backtest
    from stockbuddy.experiments.timeline import run_pilot_timeline

    row: Dict[str, Any] = {
        "ticker": ticker,
        "profile": profile,
        "batch_id": bid,
        "batch_dir": None,
        "backtest_dir": None,
        "metrics": None,
        "status": "pending",
        "error": None,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": None,
    }
    try:
        r = run_pilot_timeline(
            ticker,
            dates,
            cfg,
            selected_analysts=list(FORMAL_EVAL_V2_ANALYSTS),
            pipeline_profile=profile,
            entry="formal_eval_v2_grid",
            batch_id=bid,
        )
        row["batch_dir"] = str(r.batch_dir)
        bt = run_timeline_backtest(batch_dir=r.batch_dir, config=cfg)
        row["backtest_dir"] = str(bt.output_dir)
        row["metrics"] = json.loads(bt.metrics_path.read_text(encoding="utf-8"))
        row["status"] = "ok"
    except Exception as exc:
        row["status"] = "failed"
        row["error"] = traceback.format_exc()[-800:]
        print(f"  FAILED {ticker}/{profile}: {exc}", file=sys.stderr)
    finally:
        row["finished_at"] = datetime.now(timezone.utc).isoformat()
    return row


def run_formal_v2_grid(
    *,
    tickers: Optional[List[str]] = None,
    max_workers: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Full 10×3 grid (or subset `tickers`). Parallel workers cap via
    FORMAL_EVAL_V2_WORKERS env (default 5).
    """
    _load_project_dotenv()
    if not os.getenv("OPENROUTER_API_KEY") and not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("set OPENROUTER_API_KEY for formal-eval-v2")

    syms = list(tickers) if tickers else list(FORMAL_EVAL_V2_TICKERS)
    dates = list(FORMAL_EVAL_V2_ANALYSIS_DATES_ISO)
    cfg = formal_eval_v2_merged_config()

    tasks: List[Tuple[str, str, str]] = []
    for t in syms:
        for p in FORMAL_EVAL_V2_PROFILES:
            bid = f"formal_v2_{t}_{p}_{uuid.uuid4().hex[:8]}"
            tasks.append((t, p, bid))

    nw = _parallel_workers(len(tasks), max_workers)
    print(
        f"[formal_eval_v2] starting {len(tasks)} cells "
        f"({len(syms)} tickers × {len(FORMAL_EVAL_V2_PROFILES)} profiles), "
        f"workers={nw}, dates={dates}",
        flush=True,
    )

    out: List[Dict[str, Any]] = []
    done = 0
    with ThreadPoolExecutor(max_workers=nw) as ex:
        futs = {
            ex.submit(_grid_worker, t, p, dates, cfg, bid): (t, p)
            for t, p, bid in tasks
        }
        for fu in as_completed(futs):
            r = fu.result()
            out.append(r)
            done += 1
            status_icon = "✓" if r["status"] == "ok" else "✗"
            print(
                f"  [{done}/{len(tasks)}] {status_icon} {r['ticker']}/{r['profile']} "
                f"status={r['status']}",
                flush=True,
            )

    out.sort(
        key=lambda r: (
            _TICKER_ORDER.get(r.get("ticker", ""), 99),
            _PROFILE_ORDER.get(r.get("profile", ""), 99),
        )
    )
    return out


# ── Report formatting ──────────────────────────────────────────────────────────

def format_grid_table(rows: List[Dict[str, Any]]) -> str:
    lines = [
        "| ticker | sector | profile | B/S/H/null | trades | return | max_dd | ignored | status |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    snap = formal_eval_v2_snapshot()
    sector_map = snap.get("sector_map", {})
    for row in rows:
        m = row.get("metrics")
        tk = row.get("ticker", "—")
        sector = sector_map.get(tk, "—")
        if m:
            dist = (
                f"{m.get('num_buy_signals',0)}/"
                f"{m.get('num_sell_signals',0)}/"
                f"{m.get('num_hold_signals',0)}/"
                f"{m.get('num_null_or_other_signals',0)}"
            )
            lines.append(
                f"| {tk} | {sector} | {row['profile']} | {dist} "
                f"| {m.get('num_trades',0)} "
                f"| {m.get('total_return',0)*100:.2f}% "
                f"| {m.get('max_drawdown',0)*100:.2f}% "
                f"| {m.get('num_signals_ignored_by_protocol',0)} "
                f"| {row['status']} |"
            )
        else:
            lines.append(
                f"| {tk} | {sector} | {row['profile']} | — | — | — | — | — | {row['status']} |"
            )
    return "\n".join(lines)


def format_cross_ticker_summary(rows: List[Dict[str, Any]]) -> str:
    """Cross-ticker average per profile for all successful cells."""
    by_profile: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("metrics") and row.get("status") == "ok":
            by_profile[row["profile"]].append(row["metrics"])

    lines = [
        "| profile | n | avg_return | avg_max_dd | avg_trades | return_range |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for prof in FORMAL_EVAL_V2_PROFILES:
        ms = by_profile.get(prof, [])
        if not ms:
            lines.append(f"| {prof} | 0 | — | — | — | — |")
            continue
        rets = [m["total_return"] for m in ms]
        dds = [m["max_drawdown"] for m in ms]
        trs = [m["num_trades"] for m in ms]
        rng = f"[{min(rets)*100:.2f}%, {max(rets)*100:.2f}%]"
        lines.append(
            f"| {prof} | {len(ms)} "
            f"| {sum(rets)/len(rets)*100:.2f}% "
            f"| {sum(dds)/len(dds)*100:.2f}% "
            f"| {sum(trs)/len(trs):.1f} "
            f"| {rng} |"
        )
    return "\n".join(lines)


def format_action_dist_summary(rows: List[Dict[str, Any]]) -> str:
    """Aggregate BUY/SELL/HOLD counts across all cells, grouped by profile."""
    by_profile: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in rows:
        m = row.get("metrics")
        if not m or row.get("status") != "ok":
            continue
        p = row["profile"]
        by_profile[p]["BUY"] += m.get("num_buy_signals", 0)
        by_profile[p]["SELL"] += m.get("num_sell_signals", 0)
        by_profile[p]["HOLD"] += m.get("num_hold_signals", 0)
        by_profile[p]["NULL"] += m.get("num_null_or_other_signals", 0)
        by_profile[p]["ignored"] += m.get("num_signals_ignored_by_protocol", 0)

    lines = [
        "| profile | BUY | SELL | HOLD | NULL | total | BUY% | ignored |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for prof in FORMAL_EVAL_V2_PROFILES:
        d = by_profile.get(prof)
        if not d:
            lines.append(f"| {prof} | — | — | — | — | — | — | — |")
            continue
        total = d["BUY"] + d["SELL"] + d["HOLD"] + d["NULL"]
        buy_pct = f"{d['BUY']/total*100:.1f}%" if total else "—"
        lines.append(
            f"| {prof} | {d['BUY']} | {d['SELL']} | {d['HOLD']} | {d['NULL']} "
            f"| {total} | {buy_pct} | {d['ignored']} |"
        )
    return "\n".join(lines)


# ── Aggregate & save report pack ───────────────────────────────────────────────

def build_v2_report_pack(rows: List[Dict[str, Any]]) -> Path:
    """
    Collect all results + tier-1 metrics + gate summary into a self-contained
    report pack under experiments/formal_evidence/formal_eval_v2_{ts}/.
    Returns the pack directory.
    """
    from stockbuddy.evaluation.pilot_metrics import evaluate_batch_dir

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    pack_dir = _repo_root() / "experiments" / "formal_evidence" / f"formal_eval_v2_{ts}"
    pack_dir.mkdir(parents=True, exist_ok=True)
    metrics_dir = pack_dir / "metrics"
    metrics_dir.mkdir()

    ok_rows = [r for r in rows if r.get("status") == "ok" and r.get("metrics")]
    failed_rows = [r for r in rows if r.get("status") != "ok"]

    # 1. Protocol snapshot
    snap = formal_eval_v2_snapshot()
    snap["generated_at_utc"] = ts
    snap["n_ok_cells"] = len(ok_rows)
    snap["n_failed_cells"] = len(failed_rows)
    (pack_dir / "snapshot.json").write_text(
        json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 2. Per-cell metrics
    for row in ok_rows:
        fname = f"{row['ticker']}_{row['profile']}.json"
        m_out = {
            "ticker": row["ticker"],
            "profile": row["profile"],
            "batch_id": row.get("batch_id"),
            "batch_dir": row.get("batch_dir"),
            "backtest_dir": row.get("backtest_dir"),
            "started_at": row.get("started_at"),
            "finished_at": row.get("finished_at"),
            "metrics": row["metrics"],
        }
        (metrics_dir / fname).write_text(
            json.dumps(m_out, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # 3. Cross-ticker summary JSON
    by_profile: Dict[str, Any] = {}
    for prof in FORMAL_EVAL_V2_PROFILES:
        ms = [r["metrics"] for r in ok_rows if r["profile"] == prof]
        if not ms:
            by_profile[prof] = {"n": 0}
            continue
        rets = [m["total_return"] for m in ms]
        dds = [m["max_drawdown"] for m in ms]
        trs = [m["num_trades"] for m in ms]
        by_profile[prof] = {
            "n": len(ms),
            "mean_total_return": sum(rets) / len(rets),
            "median_total_return": sorted(rets)[len(rets) // 2],
            "mean_max_drawdown": sum(dds) / len(dds),
            "mean_num_trades": sum(trs) / len(trs),
            "return_min": min(rets),
            "return_max": max(rets),
            "n_positive_return": sum(1 for r in rets if r > 0),
            "action_totals": {
                "BUY": sum(m.get("num_buy_signals", 0) for m in ms),
                "SELL": sum(m.get("num_sell_signals", 0) for m in ms),
                "HOLD": sum(m.get("num_hold_signals", 0) for m in ms),
                "ignored": sum(m.get("num_signals_ignored_by_protocol", 0) for m in ms),
            },
        }

    summary: Dict[str, Any] = {
        "title": "formal_eval_v2 — 10-ticker 6-month formal evidence run",
        "generated_at_utc": ts,
        "protocol": snap,
        "run_completeness": {
            "total_cells": len(rows),
            "ok": len(ok_rows),
            "failed": len(failed_rows),
            "success_rate": len(ok_rows) / len(rows) if rows else 0.0,
            "failed_cells": [
                {"ticker": r["ticker"], "profile": r["profile"], "error": (r.get("error") or "")[:300]}
                for r in failed_rows
            ],
        },
        "cross_ticker_by_profile": by_profile,
        "report_readiness_zh": (
            "10只标的×3 profile×6月均跑通时，本结果可作为 formal main evidence 主表；"
            "若部分 cell 失败（success_rate<0.85），建议降级为 strong preliminary evidence。"
        ),
    }
    (pack_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 4. Tier-1 (behavior/risk/process) for each batch
    tier1_rows: List[Dict[str, Any]] = []
    for row in ok_rows:
        bd = row.get("batch_dir")
        if bd and Path(bd).is_dir():
            try:
                t1 = evaluate_batch_dir(
                    Path(bd),
                    pipeline_profile=row["profile"],
                )
                t1["ticker"] = row["ticker"]
                t1["profile"] = row["profile"]
                tier1_rows.append(t1)
            except Exception as e:
                tier1_rows.append(
                    {"ticker": row["ticker"], "profile": row["profile"], "error": str(e)[:200]}
                )

    (pack_dir / "tier1_behavior_risk_process.json").write_text(
        json.dumps(
            {
                "generated_at_utc": ts,
                "n_batches_evaluated": len(tier1_rows),
                "rows": tier1_rows,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    # 5. Raw grid results (full, for reproducibility)
    (pack_dir / "grid_results_raw.json").write_text(
        json.dumps(
            {
                "generated_at_utc": ts,
                "rows": [
                    {k: v for k, v in r.items() if k != "metrics"}
                    for r in rows
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    # 6. Manifest
    manifest = {
        "pack_dir": str(pack_dir),
        "generated_at_utc": ts,
        "evidence_tier": "formal_main" if len(ok_rows) / max(len(rows), 1) >= 0.85 else "strong_preliminary",
        "files": {
            "snapshot.json": "冻结协议元数据（10只标的、6月窗口、dates、profiles、fee）",
            "summary.json": "主汇总：run completeness + cross-ticker by-profile aggregates",
            "tier1_behavior_risk_process.json": "行为/风险/过程可靠性逐 batch 详情",
            "metrics/*.json": "每cell（ticker×profile）完整 backtest metrics",
            "grid_results_raw.json": "原始 grid 运行记录（含 batch_dir 路径）",
        },
    }
    (pack_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return pack_dir


# ── CLI entry point ─────────────────────────────────────────────────────────────

def main(argv: Optional[List[str]] = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]

    if not argv or argv[0] == "help":
        print(
            "usage: python -m stockbuddy.experiments.formal_eval_v2 <command>\n"
            "commands:\n"
            "  verify-dates   — check FORMAL_EVAL_V2_ANALYSIS_DATES_ISO vs 0700.HK calendar\n"
            "  smoke          — structural checks only (no LLM, no API key)\n"
            "  run            — launch full 10×3 grid (overnight; needs API key)\n"
            "  run --tickers 0700,1299  — subset run\n"
            "  run --workers N  — override parallel worker count\n"
            "\n"
            "env vars:\n"
            "  FORMAL_EVAL_V2_WORKERS  parallel cap (default 5)\n"
            "  DEEP_THINK_LLM / QUICK_THINK_LLM  model overrides",
            file=sys.stderr,
        )
        return 0

    if argv[0] == "verify-dates":
        assert_frozen_dates_match_calendar()
        print("OK — FORMAL_EVAL_V2_ANALYSIS_DATES_ISO matches 0700.HK calendar")
        print("dates:", FORMAL_EVAL_V2_ANALYSIS_DATES_ISO)
        return 0

    if argv[0] == "smoke":
        assert_frozen_dates_match_calendar()
        snap = formal_eval_v2_snapshot()
        print("snapshot OK:", json.dumps(snap, indent=2, ensure_ascii=False))
        return 0

    if argv[0] == "run":
        # parse optional flags
        tickers_override: Optional[List[str]] = None
        workers_override: Optional[int] = None
        i = 1
        while i < len(argv):
            if argv[i] == "--tickers" and i + 1 < len(argv):
                tickers_override = [t.strip() for t in argv[i + 1].split(",")]
                i += 2
            elif argv[i] == "--workers" and i + 1 < len(argv):
                workers_override = int(argv[i + 1])
                i += 2
            else:
                i += 1

        started = datetime.now(timezone.utc)
        rows = run_formal_v2_grid(
            tickers=tickers_override,
            max_workers=workers_override,
        )

        elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        ok = sum(1 for r in rows if r["status"] == "ok")
        print(f"\n[formal_eval_v2] done: {ok}/{len(rows)} cells ok, elapsed={elapsed:.0f}s")

        print("\n=== Per-cell grid ===")
        print(format_grid_table(rows))
        print("\n=== Cross-ticker summary ===")
        print(format_cross_ticker_summary(rows))
        print("\n=== Action distribution ===")
        print(format_action_dist_summary(rows))

        print("\n[formal_eval_v2] building report pack...")
        pack_dir = build_v2_report_pack(rows)
        print(f"[formal_eval_v2] report pack: {pack_dir}")

        # also update preliminary_results pointer
        ptr_path = (
            _repo_root() / "experiments" / "formal_evidence" / "latest_v2_pack.txt"
        )
        ptr_path.write_text(str(pack_dir), encoding="utf-8")
        print(f"[formal_eval_v2] latest pointer: {ptr_path}")

        return 0 if ok > 0 else 1

    print(f"unknown command: {argv[0]}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
