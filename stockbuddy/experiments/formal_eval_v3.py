"""
Formal evaluation v3 — signal quality first, weekly frequency, EODHD news.

Period  : 2024-09-02 ~ 2025-02-28 (6 months, HK bull + consolidation)
Universe: 4 HK stocks across 4 sectors
Profiles: full_system only (baselines via backtrader in a later phase)
Calendar: weekly first HK session, proxy 0700.HK
Analysts: market, fundamentals, news, social (all 4)

Usage:
  python -m stockbuddy.experiments.formal_eval_v3 verify-dates
  python -m stockbuddy.experiments.formal_eval_v3 smoke
  python -m stockbuddy.experiments.formal_eval_v3 run --tickers 9988
  python -m stockbuddy.experiments.formal_eval_v3 run                   # all 4 tickers
  python -m stockbuddy.experiments.formal_eval_v3 signal-quality --batch-dir <path>
  python -m stockbuddy.experiments.formal_eval_v3 layer1-pooled
"""

from __future__ import annotations

import json
import os
import sys
import traceback
import uuid

try:
    import fcntl  # noqa: F401 — parallel ticker runs: atomic progress.json

    _HAS_FCNTL = True
except ImportError:
    _HAS_FCNTL = False
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from stockbuddy.default_config import DEFAULT_CONFIG
from stockbuddy.evaluation.prices import (
    fetch_ohlc,
    normalize_hk_symbol,
    trading_days_index,
)

FORMAL_EVAL_V3_VERSION = "v3"

FORMAL_EVAL_V3_TICKERS: List[str] = [
    "9988",  # Alibaba   — E-commerce
    "1211",  # BYD       — Auto / EV
    "0700",  # Tencent   — Tech / Internet
    "0005",  # HSBC      — Banking / Finance
]

FORMAL_EVAL_V3_PERIOD_START = "2024-09-02"
FORMAL_EVAL_V3_PERIOD_END = "2025-02-28"

FORMAL_EVAL_V3_ANALYSTS: List[str] = [
    "market",
    "fundamentals",
    "news",
    "social",
]

FORMAL_EVAL_V3_PROFILE = "full_system"

# Weekly first-session dates from 0700.HK calendar; frozen 2026-04-06.
# Re-verify with `verify-dates` command.
FORMAL_EVAL_V3_ANALYSIS_DATES_ISO: List[str] = [
    "2024-09-02", "2024-09-09", "2024-09-16", "2024-09-23", "2024-09-30",
    "2024-10-07", "2024-10-14", "2024-10-21", "2024-10-28",
    "2024-11-04", "2024-11-11", "2024-11-18", "2024-11-25",
    "2024-12-02", "2024-12-09", "2024-12-16", "2024-12-23", "2024-12-30",
    "2025-01-06", "2025-01-13", "2025-01-20", "2025-01-27",
    "2025-02-03", "2025-02-10", "2025-02-17", "2025-02-24",
]

_PROGRESS_FILE = "formal_v3_progress.json"


# ── Date computation ─────────────────────────────────────────────


def _period_dates() -> Tuple[date, date]:
    s = FORMAL_EVAL_V3_PERIOD_START.split("-")
    e = FORMAL_EVAL_V3_PERIOD_END.split("-")
    return date(int(s[0]), int(s[1]), int(s[2])), date(int(e[0]), int(e[1]), int(e[2]))


def compute_weekly_dates() -> List[str]:
    """First HK trading session per ISO week in the evaluation period.
    Uses 0700.HK as the calendar proxy."""
    lo, hi = _period_dates()
    sym = normalize_hk_symbol("0700")
    df = fetch_ohlc(sym, lo, hi)
    if df.empty:
        raise RuntimeError("No OHLC data for 0700.HK in evaluation period")
    days = trading_days_index(df)

    seen_weeks: set[Tuple[int, int]] = set()
    out: List[str] = []
    for d in days:
        iso_year, iso_week, _ = d.isocalendar()
        key = (iso_year, iso_week)
        if key not in seen_weeks:
            seen_weeks.add(key)
            out.append(d.isoformat())
    return out


def _get_frozen_or_compute_dates() -> List[str]:
    if FORMAL_EVAL_V3_ANALYSIS_DATES_ISO:
        return list(FORMAL_EVAL_V3_ANALYSIS_DATES_ISO)
    return compute_weekly_dates()


# ── Config ───────────────────────────────────────────────────────


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(_repo_root() / ".env", override=True)


def formal_eval_v3_snapshot(dates: List[str]) -> Dict[str, Any]:
    return {
        "version": FORMAL_EVAL_V3_VERSION,
        "tickers": list(FORMAL_EVAL_V3_TICKERS),
        "period_start": FORMAL_EVAL_V3_PERIOD_START,
        "period_end": FORMAL_EVAL_V3_PERIOD_END,
        "analysis_dates": dates,
        "selected_analysts": list(FORMAL_EVAL_V3_ANALYSTS),
        "profile": FORMAL_EVAL_V3_PROFILE,
        "absolute_no_news": False,
        "memory_disabled": True,
        "max_debate_rounds": 2,
        "max_risk_discuss_rounds": 2,
        "calendar_proxy": "0700.HK",
        "n_analysis_dates": len(dates),
        "n_tickers": len(FORMAL_EVAL_V3_TICKERS),
        "sector_map": {
            "9988": "E-commerce",
            "1211": "Auto/EV",
            "0700": "Tech/Internet",
            "0005": "Banking/Finance",
        },
    }


def formal_eval_v3_config(extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    dates = _get_frozen_or_compute_dates()
    base: Dict[str, Any] = {
        **DEFAULT_CONFIG,
        "memory_enabled": False,
        "absolute_no_news": False,
        "max_debate_rounds": 2,
        "max_risk_discuss_rounds": 2,
        "risk_gates_enabled": False,  # G1-G4 disabled; raw signals for IC evaluation
        "formal_eval_v3": True,
        "formal_eval_v3_snapshot": formal_eval_v3_snapshot(dates),
        "tool_vendors": {
            **DEFAULT_CONFIG.get("tool_vendors", {}),
            "get_news": "merged",
        },
    }
    if os.getenv("DEEP_THINK_LLM"):
        base["deep_think_llm"] = os.environ["DEEP_THINK_LLM"]
    if os.getenv("QUICK_THINK_LLM"):
        base["quick_think_llm"] = os.environ["QUICK_THINK_LLM"]
    if extra:
        base.update(extra)
    return base


# ── Progress / Resume ────────────────────────────────────────────


def _progress_path() -> Path:
    return _repo_root() / "experiments" / "formal_evidence" / _PROGRESS_FILE


def _load_progress() -> Dict[str, str]:
    p = _progress_path()
    if not p.is_file():
        return {}
    if not _HAS_FCNTL:
        return json.loads(p.read_text(encoding="utf-8"))
    with open(p, "r", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_SH)
        try:
            return json.loads(f.read())
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def _merge_progress_updates(updates: Dict[str, str]) -> None:
    """Read-modify-write under lock so parallel `run --tickers X` do not clobber."""
    p = _progress_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    if not _HAS_FCNTL:
        prog = _load_progress()
        prog.update(updates)
        p.write_text(json.dumps(prog, ensure_ascii=False, indent=2), encoding="utf-8")
        return
    with open(p, "a+", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.seek(0)
            raw = f.read()
            prog = json.loads(raw) if raw.strip() else {}
            prog.update(updates)
            f.seek(0)
            f.truncate()
            f.write(json.dumps(prog, ensure_ascii=False, indent=2))
            f.flush()
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def _cell_key(ticker: str, date_iso: str) -> str:
    return f"{ticker}_{FORMAL_EVAL_V3_PROFILE}_{date_iso}"


def seed_progress_from_artifacts(
    tickers: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Set progress ok from experiments/<run_id>/decision.json (v3 calendar only).

    Use after a crashed run so `run --tickers X` skips weeks already on disk.
    """
    valid_dates: Set[str] = set(FORMAL_EVAL_V3_ANALYSIS_DATES_ISO)
    root = _repo_root() / "experiments"
    want: Set[str] = set(tickers) if tickers else set(FORMAL_EVAL_V3_TICKERS)
    best_m: Dict[Tuple[str, str], float] = {}
    for p in root.glob("*/decision.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            tk = str(data.get("ticker") or "").strip()
            ad = data.get("analysis_date")
            if not tk or not ad:
                continue
            ad = str(ad).strip()
            if tk not in want or ad not in valid_dates:
                continue
            mt = p.stat().st_mtime
            key = (tk, ad)
            if key not in best_m or mt > best_m[key]:
                best_m[key] = mt
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            continue
    updates = {_cell_key(tk, ad): "ok" for (tk, ad) in best_m}
    if updates:
        _merge_progress_updates(updates)
    by_tk: Dict[str, int] = {}
    for (tk, _) in best_m:
        by_tk[tk] = by_tk.get(tk, 0) + 1
    return {"n_seeded": len(updates), "per_ticker": by_tk}


def merge_formal_v3_decisions_jsonl(
    ticker: str,
    out_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """26 rows aligned to FORMAL_EVAL_V3_ANALYSIS_DATES_ISO; per date pick newest decision.json mtime."""
    valid_dates = FORMAL_EVAL_V3_ANALYSIS_DATES_ISO
    date_set = set(valid_dates)
    root = _repo_root() / "experiments"
    best: Dict[str, Tuple[float, Path, Dict[str, Any]]] = {}
    for p in root.glob("*/decision.json"):
        try:
            dec = json.loads(p.read_text(encoding="utf-8"))
            tk = str(dec.get("ticker") or "").strip()
            if tk != ticker:
                continue
            ad = str(dec.get("analysis_date") or "").strip()
            if ad not in date_set:
                continue
            rdir = p.parent
            mt = p.stat().st_mtime
            if ad not in best or mt > best[ad][0]:
                best[ad] = (mt, rdir, dec)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            continue

    if out_dir is None:
        batches_root = _repo_root() / "experiments" / "batches"
        cands = sorted(
            batches_root.glob(f"formal_v3_{ticker}_*"),
            key=lambda x: x.stat().st_mtime,
            reverse=True,
        )
        if not cands:
            raise FileNotFoundError(
                f"no experiments/batches/formal_v3_{ticker}_*; pass --batch-dir"
            )
        out_dir = cands[0]
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    merged_bid = f"formal_v3_{ticker}_merged"
    lines: List[Dict[str, Any]] = []
    missing: List[str] = []
    for ad in valid_dates:
        if ad not in best:
            missing.append(ad)
            continue
        _, rdir, dec = best[ad]
        dpath = rdir / "decision.json"
        lines.append(
            {
                "batch_id": merged_bid,
                "run_id": str(dec.get("run_id") or rdir.name),
                "ticker": ticker,
                "analysis_date": ad,
                "experiment_dir": str(rdir.resolve()),
                "decision_json": str(dpath.resolve()),
                "action": dec.get("action"),
                "direction_score": dec.get("direction_score"),
                "asset_type": dec.get("asset_type"),
                "confidence": dec.get("confidence"),
                "parsed_action_pre_gate": dec.get("parsed_action_pre_gate"),
                "parsed_action_post_gate": dec.get("parsed_action_post_gate"),
                "news_status": dec.get("news_status"),
                "gate_summary": dec.get("gate_summary"),
                "blocked_by_risk_gate": dec.get("blocked_by_risk_gate"),
                "rationale_summary": dec.get("rationale_summary"),
                "status": "ok",
                "error": None,
            }
        )

    outp = out_dir / "decisions_merged_26w.jsonl"
    with open(outp, "w", encoding="utf-8") as f:
        for row in lines:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    report: Dict[str, Any] = {
        "ticker": ticker,
        "out": str(outp.resolve()),
        "n_rows": len(lines),
        "expected": len(valid_dates),
        "missing_dates": missing,
        "complete": len(missing) == 0,
    }
    (out_dir / "merge_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def _latest_merged_decisions_path(ticker: str) -> Path:
    batches_root = _repo_root() / "experiments" / "batches"
    cands = sorted(
        batches_root.glob(f"formal_v3_{ticker}_*"),
        key=lambda x: x.stat().st_mtime,
        reverse=True,
    )
    for b in cands:
        p = b / "decisions_merged_26w.jsonl"
        if p.is_file():
            return p
    raise FileNotFoundError(
        f"no decisions_merged_26w.jsonl under experiments/batches/formal_v3_{ticker}_*"
    )


def run_layer1_pooled() -> Dict[str, Any]:
    """Signal quality (Layer 1) on pooled 4×26 merged rows; per row uses that ticker’s OHLC."""
    _load_dotenv()
    from stockbuddy.evaluation.signal_quality import evaluate_signal_quality

    ev_root = _repo_root() / "experiments" / "formal_evidence"
    ev_root.mkdir(parents=True, exist_ok=True)
    combined = ev_root / "formal_v3_layer1_pooled_decisions.jsonl"
    paths: List[Path] = []
    all_objs: List[Dict[str, Any]] = []
    for tk in FORMAL_EVAL_V3_TICKERS:
        p = _latest_merged_decisions_path(tk)
        paths.append(p)
        for line in p.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if s:
                all_objs.append(json.loads(s))
    with open(combined, "w", encoding="utf-8") as f:
        for obj in all_objs:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")
    report = evaluate_signal_quality(decisions_jsonl=combined)
    rep_path = ev_root / "formal_v3_layer1_pooled_report.json"
    rep_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "combined_jsonl": str(combined.resolve()),
        "report_json": str(rep_path.resolve()),
        "n_rows": len(all_objs),
        "sources": [str(x.resolve()) for x in paths],
        "go_no_go_overall": report.get("go_no_go", {}).get("overall"),
    }


# ── Ablation variants ────────────────────────────────────────────

ABLATION_VARIANTS: Dict[str, Dict[str, Any]] = {
    "single_agent": {
        "pipeline_profile": "single_agent",
        "selected_analysts": ["market"],
        "label": "Market only, no debate/risk",
    },
    "market_debate": {
        "pipeline_profile": "full_system",
        "selected_analysts": ["market"],
        "label": "Market only + debate + risk",
    },
    "market_fund": {
        "pipeline_profile": "full_system",
        "selected_analysts": ["market", "fundamentals"],
        "label": "Market+Fundamentals + debate + risk",
    },
}


def _ablation_cell_key(variant: str, ticker: str, date_iso: str) -> str:
    return f"abl_{variant}_{ticker}_{date_iso}"


def _ablation_progress_path() -> Path:
    return _repo_root() / "experiments" / "formal_evidence" / "ablation_progress.json"


def _load_ablation_progress() -> Dict[str, str]:
    p = _ablation_progress_path()
    if not p.is_file():
        return {}
    if not _HAS_FCNTL:
        return json.loads(p.read_text(encoding="utf-8"))
    with open(p, "r", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_SH)
        try:
            return json.loads(f.read())
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def _merge_ablation_progress(updates: Dict[str, str]) -> None:
    p = _ablation_progress_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    if not _HAS_FCNTL:
        prog = _load_ablation_progress()
        prog.update(updates)
        p.write_text(json.dumps(prog, ensure_ascii=False, indent=2), encoding="utf-8")
        return
    with open(p, "a+", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.seek(0)
            raw = f.read()
            prog = json.loads(raw) if raw.strip() else {}
            prog.update(updates)
            f.seek(0)
            f.truncate()
            f.write(json.dumps(prog, ensure_ascii=False, indent=2))
            f.flush()
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def run_ablation_variant(
    variant: str,
    ticker: str,
    *,
    force: bool = False,
) -> Dict[str, Any]:
    """Run one ablation variant for one ticker across all v3 dates."""
    from stockbuddy.experiments.timeline import run_pilot_timeline

    spec = ABLATION_VARIANTS[variant]
    dates = _get_frozen_or_compute_dates()
    cfg = formal_eval_v3_config()
    prog = _load_ablation_progress()
    bid = f"ablation_{variant}_{ticker}_{uuid.uuid4().hex[:8]}"

    if force:
        run_dates = list(dates)
    else:
        run_dates = [
            d for d in dates
            if prog.get(_ablation_cell_key(variant, ticker, d)) != "ok"
        ]
    skipped = len(dates) - len(run_dates)
    if skipped:
        print(f"  [abl/{variant}/{ticker}] resume: {skipped} done, {len(run_dates)} left")
    if not run_dates:
        return {"variant": variant, "ticker": ticker, "status": "all_complete",
                "skipped": skipped, "batch_dir": None}

    result: Dict[str, Any] = {
        "variant": variant, "ticker": ticker, "batch_id": bid,
        "batch_dir": None, "n_dates_total": len(dates),
        "n_dates_run": len(run_dates), "n_dates_skipped": skipped,
        "status": "pending", "error": None,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": None,
    }
    try:
        r = run_pilot_timeline(
            ticker, run_dates, cfg,
            selected_analysts=spec["selected_analysts"],
            pipeline_profile=spec["pipeline_profile"],
            entry=f"ablation_{variant}",
            batch_id=bid,
        )
        result["batch_dir"] = str(r.batch_dir)
        result["status"] = "ok"
        _merge_ablation_progress(
            {_ablation_cell_key(variant, ticker, d): "ok" for d in run_dates}
        )
    except Exception as exc:
        result["status"] = "failed"
        result["error"] = traceback.format_exc()[-800:]
        print(f"  FAILED abl/{variant}/{ticker}: {exc}", file=sys.stderr)
    finally:
        result["finished_at"] = datetime.now(timezone.utc).isoformat()
    return result


# ── Grid runner ──────────────────────────────────────────────────


def _run_single_ticker(
    ticker: str,
    dates: List[str],
    cfg: Dict[str, Any],
    *,
    force: bool = False,
) -> Dict[str, Any]:
    """Run full_system for one ticker across all weekly dates, with resume."""
    from stockbuddy.experiments.timeline import run_pilot_timeline

    prog = _load_progress()
    bid = f"formal_v3_{ticker}_{uuid.uuid4().hex[:8]}"

    if force:
        run_dates = list(dates)
    else:
        run_dates = [d for d in dates if prog.get(_cell_key(ticker, d)) != "ok"]

    skipped = len(dates) - len(run_dates)
    if skipped > 0:
        print(f"  [{ticker}] resuming: {skipped} dates already complete, {len(run_dates)} remaining")

    if not run_dates:
        return {
            "ticker": ticker,
            "status": "all_complete",
            "skipped": skipped,
            "batch_dir": None,
        }

    result: Dict[str, Any] = {
        "ticker": ticker,
        "batch_id": bid,
        "batch_dir": None,
        "n_dates_total": len(dates),
        "n_dates_run": len(run_dates),
        "n_dates_skipped": skipped,
        "status": "pending",
        "error": None,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": None,
    }

    try:
        r = run_pilot_timeline(
            ticker,
            run_dates,
            cfg,
            selected_analysts=list(FORMAL_EVAL_V3_ANALYSTS),
            pipeline_profile=FORMAL_EVAL_V3_PROFILE,
            entry="formal_eval_v3",
            batch_id=bid,
        )
        result["batch_dir"] = str(r.batch_dir)
        result["status"] = "ok"

        _merge_progress_updates(
            {_cell_key(ticker, d): "ok" for d in run_dates}
        )

    except Exception as exc:
        result["status"] = "failed"
        result["error"] = traceback.format_exc()[-800:]
        print(f"  FAILED {ticker}: {exc}", file=sys.stderr)
    finally:
        result["finished_at"] = datetime.now(timezone.utc).isoformat()

    return result


def run_formal_v3(
    *,
    tickers: Optional[List[str]] = None,
    force: bool = False,
) -> List[Dict[str, Any]]:
    _load_dotenv()
    if not os.getenv("OPENROUTER_API_KEY") and not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("set OPENROUTER_API_KEY or OPENAI_API_KEY")
    if not (os.getenv("EODHD_API_KEY") or "").strip():
        print("WARNING: EODHD_API_KEY not set; historical news will be empty", file=sys.stderr)

    syms = list(tickers) if tickers else list(FORMAL_EVAL_V3_TICKERS)
    dates = _get_frozen_or_compute_dates()
    cfg = formal_eval_v3_config()

    print(
        f"[formal_eval_v3] {len(syms)} tickers × {len(dates)} weeks = {len(syms)*len(dates)} signals",
        flush=True,
    )
    print(f"  period: {dates[0]} .. {dates[-1]}", flush=True)
    print(f"  analysts: {FORMAL_EVAL_V3_ANALYSTS}", flush=True)
    print(f"  profile: {FORMAL_EVAL_V3_PROFILE}", flush=True)
    if force:
        print("  --force: re-running all dates (ignoring progress)", flush=True)

    results: List[Dict[str, Any]] = []
    for i, tk in enumerate(syms):
        print(f"\n[{i+1}/{len(syms)}] Running {tk}...", flush=True)
        r = _run_single_ticker(tk, dates, cfg, force=force)
        results.append(r)
        status = r["status"]
        print(f"  [{tk}] {status}", flush=True)
        if r.get("batch_dir"):
            print(f"  [{tk}] batch_dir: {r['batch_dir']}", flush=True)

    return results


# ── CLI ──────────────────────────────────────────────────────────


def main(argv: Optional[List[str]] = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]

    if not argv or argv[0] == "help":
        print(
            "usage: python -m stockbuddy.experiments.formal_eval_v3 <command>\n"
            "commands:\n"
            "  verify-dates      — compute weekly dates from 0700.HK and print\n"
            "  smoke             — structural checks (no LLM)\n"
            "  run               — run all 4 tickers sequentially\n"
            "  run --tickers 9988       — run single ticker (pilot)\n"
            "  run --tickers 9988,1211  — run subset\n"
            "  run --force              — ignore progress, re-run all\n"
            "  seed-progress [--tickers 1211,0700] — mark ok from experiments/*/decision.json\n"
            "  merge-decisions --ticker 1211 [--batch-dir <path>] — 26w jsonl from artifacts\n"
            "  layer1-pooled     — L1 signal_quality on 4× merged 26w (writes formal_evidence/)\n"
            "  ablation --variant single_agent [--ticker 9988] [--force] — run one ablation variant\n"
            "  ablation-progress — show ablation resume progress\n"
            "  signal-quality --batch-dir <path>  — evaluate signal quality\n"
            "  progress          — show resume progress\n",
            file=sys.stderr,
        )
        return 0

    if argv[0] == "verify-dates":
        dates = compute_weekly_dates()
        print(f"OK — {len(dates)} weekly dates for 0700.HK")
        for i, d in enumerate(dates):
            print(f"  {i+1:2d}. {d}")
        return 0

    if argv[0] == "smoke":
        dates = compute_weekly_dates()
        snap = formal_eval_v3_snapshot(dates)
        print(f"Snapshot OK: {len(dates)} weeks, {len(FORMAL_EVAL_V3_TICKERS)} tickers")
        print(json.dumps(snap, indent=2, ensure_ascii=False))
        _load_dotenv()
        eodhd = bool((os.getenv("EODHD_API_KEY") or "").strip())
        openrouter = bool(os.getenv("OPENROUTER_API_KEY"))
        print(f"\nAPI keys: EODHD={'OK' if eodhd else 'MISSING'}, OpenRouter={'OK' if openrouter else 'MISSING'}")
        return 0

    if argv[0] == "run":
        tickers_override: Optional[List[str]] = None
        force = False
        i = 1
        while i < len(argv):
            if argv[i] == "--tickers" and i + 1 < len(argv):
                tickers_override = [t.strip() for t in argv[i + 1].split(",")]
                i += 2
            elif argv[i] == "--force":
                force = True
                i += 1
            else:
                i += 1

        started = datetime.now(timezone.utc)
        results = run_formal_v3(tickers=tickers_override, force=force)
        elapsed = (datetime.now(timezone.utc) - started).total_seconds()

        ok = sum(1 for r in results if r["status"] in ("ok", "all_complete"))
        print(f"\n[formal_eval_v3] done: {ok}/{len(results)} tickers ok, elapsed={elapsed:.0f}s")
        for r in results:
            print(f"  {r['ticker']}: {r['status']}", end="")
            if r.get("batch_dir"):
                print(f" -> {r['batch_dir']}", end="")
            print()

        return 0 if ok > 0 else 1

    if argv[0] == "seed-progress":
        tickers_override: Optional[List[str]] = None
        i = 1
        while i < len(argv):
            if argv[i] == "--tickers" and i + 1 < len(argv):
                tickers_override = [t.strip() for t in argv[i + 1].split(",")]
                i += 2
            else:
                i += 1
        out = seed_progress_from_artifacts(tickers=tickers_override)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0

    if argv[0] == "merge-decisions":
        tickers_m: List[str] = []
        batch_dir_m: Optional[Path] = None
        i = 1
        while i < len(argv):
            if argv[i] == "--ticker" and i + 1 < len(argv):
                tickers_m.append(argv[i + 1].strip())
                i += 2
            elif argv[i] == "--tickers" and i + 1 < len(argv):
                tickers_m.extend(t.strip() for t in argv[i + 1].split(",") if t.strip())
                i += 2
            elif argv[i] == "--batch-dir" and i + 1 < len(argv):
                batch_dir_m = Path(argv[i + 1])
                i += 2
            else:
                i += 1
        if not tickers_m:
            print("ERROR: --ticker or --tickers required", file=sys.stderr)
            return 2
        if len(tickers_m) > 1 and batch_dir_m is not None:
            print("ERROR: --batch-dir only with a single --ticker", file=sys.stderr)
            return 2
        rc = 0
        for tk in tickers_m:
            try:
                rep = merge_formal_v3_decisions_jsonl(
                    tk, out_dir=batch_dir_m if len(tickers_m) == 1 else None
                )
                print(json.dumps(rep, ensure_ascii=False, indent=2))
                if not rep.get("complete"):
                    rc = 1
            except FileNotFoundError as e:
                print(f"ERROR {tk}: {e}", file=sys.stderr)
                rc = 1
        return rc

    if argv[0] == "layer1-pooled":
        try:
            out = run_layer1_pooled()
        except FileNotFoundError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            print("hint: run merge-decisions for each ticker first", file=sys.stderr)
            return 1
        except Exception as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            traceback.print_exc()
            return 1
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0

    if argv[0] == "signal-quality":
        from stockbuddy.evaluation.signal_quality import evaluate_signal_quality

        batch_dir = None
        out_path = None
        i = 1
        while i < len(argv):
            if argv[i] == "--batch-dir" and i + 1 < len(argv):
                batch_dir = Path(argv[i + 1])
                i += 2
            elif argv[i] == "--out" and i + 1 < len(argv):
                out_path = Path(argv[i + 1])
                i += 2
            else:
                i += 1

        if batch_dir is None:
            print("ERROR: --batch-dir required", file=sys.stderr)
            return 2

        report = evaluate_signal_quality(batch_dir=batch_dir)
        text = json.dumps(report, ensure_ascii=False, indent=2)
        if out_path:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(text, encoding="utf-8")
            print(f"Written to {out_path}")
        else:
            print(text)

        go = report.get("go_no_go", {})
        print(f"\n{'='*50}", file=sys.stderr)
        print(f"Signal Quality: {go.get('overall', '?')}", file=sys.stderr)
        for k, v in go.items():
            if k in ("primary_horizon", "overall"):
                continue
            status = "PASS" if v.get("pass") else "FAIL"
            print(f"  {k}: {status}", file=sys.stderr)
        print(f"{'='*50}", file=sys.stderr)
        return 0

    if argv[0] == "ablation":
        variant_name: Optional[str] = None
        abl_ticker = "9988"
        abl_force = False
        i = 1
        while i < len(argv):
            if argv[i] == "--variant" and i + 1 < len(argv):
                variant_name = argv[i + 1].strip()
                i += 2
            elif argv[i] == "--ticker" and i + 1 < len(argv):
                abl_ticker = argv[i + 1].strip()
                i += 2
            elif argv[i] == "--force":
                abl_force = True
                i += 1
            else:
                i += 1
        if variant_name is None:
            print(
                f"ERROR: --variant required. choices: {', '.join(ABLATION_VARIANTS)}",
                file=sys.stderr,
            )
            return 2
        if variant_name not in ABLATION_VARIANTS:
            print(
                f"ERROR: unknown variant '{variant_name}'. "
                f"choices: {', '.join(ABLATION_VARIANTS)}",
                file=sys.stderr,
            )
            return 2
        _load_dotenv()
        if not os.getenv("OPENROUTER_API_KEY") and not os.getenv("OPENAI_API_KEY"):
            print("ERROR: set OPENROUTER_API_KEY or OPENAI_API_KEY", file=sys.stderr)
            return 1
        spec = ABLATION_VARIANTS[variant_name]
        print(
            f"[ablation] variant={variant_name} ticker={abl_ticker}",
            flush=True,
        )
        print(
            f"  profile={spec['pipeline_profile']} analysts={spec['selected_analysts']}",
            flush=True,
        )
        started = datetime.now(timezone.utc)
        r = run_ablation_variant(variant_name, abl_ticker, force=abl_force)
        elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        print(json.dumps(r, ensure_ascii=False, indent=2))
        print(f"\n[ablation] {variant_name}/{abl_ticker}: {r['status']}, {elapsed:.0f}s")
        return 0 if r["status"] in ("ok", "all_complete") else 1

    if argv[0] == "ablation-progress":
        prog = _load_ablation_progress()
        if not prog:
            print("No ablation progress recorded yet.")
            return 0
        by_var: Dict[str, Dict[str, int]] = {}
        for k, v in prog.items():
            parts = k.split("_", 3)  # abl_<variant>_<ticker>_<date>
            if len(parts) < 4 or v != "ok":
                continue
            var = parts[1]
            tk = parts[2]
            by_var.setdefault(var, {}).setdefault(tk, 0)
            by_var[var][tk] += 1
        n_dates = len(FORMAL_EVAL_V3_ANALYSIS_DATES_ISO)
        for var in sorted(by_var):
            for tk, n in sorted(by_var[var].items()):
                print(f"  {var}/{tk}: {n}/{n_dates}")
        return 0

    if argv[0] == "progress":
        prog = _load_progress()
        if not prog:
            print("No progress recorded yet.")
            return 0
        ok = sum(1 for v in prog.values() if v == "ok")
        total = len(prog)
        print(f"Progress: {ok}/{total} cells complete")
        by_ticker: Dict[str, int] = {}
        for k, v in prog.items():
            tk = k.split("_")[0]
            if v == "ok":
                by_ticker[tk] = by_ticker.get(tk, 0) + 1
        for tk, n in sorted(by_ticker.items()):
            print(f"  {tk}: {n} dates complete")
        return 0

    print(f"unknown command: {argv[0]}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
