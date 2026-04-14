"""
Formal evaluation v1 — frozen protocol (single import for runs + smoke).

Tickers share one calendar: monthly first session on 0700.HK bars (Jun–Aug 2024).
"""

from __future__ import annotations

import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
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

FORMAL_EVAL_V1_VERSION = "v1"

# 0700/1299/0941: pilot core; 0388/9988: liquid HK add-ons (same calendar dates).
FORMAL_EVAL_V1_TICKERS: List[str] = ["0700", "1299", "0941", "0388", "9988"]

FORMAL_EVAL_V1_PERIOD_START = "2024-06-01"
FORMAL_EVAL_V1_PERIOD_END = "2024-08-31"

# First HK session per calendar month in [period_start..period_end]; 0700.HK calendar.
FORMAL_EVAL_V1_ANALYSIS_DATES_ISO: List[str] = [
    "2024-06-03",
    "2024-07-02",
    "2024-08-01",
]

FORMAL_EVAL_V1_ANALYSTS: List[str] = ["market", "fundamentals"]

FORMAL_EVAL_V1_PROFILES: Tuple[str, ...] = (
    "buy_and_hold",
    "single_agent",
    "full_system",
)

_PROFILE_ORDER: Dict[str, int] = {p: i for i, p in enumerate(FORMAL_EVAL_V1_PROFILES)}
_TICKER_ORDER: Dict[str, int] = {t: i for i, t in enumerate(FORMAL_EVAL_V1_TICKERS)}

# Cheap / common on OpenRouter; single ping each (not formal_eval design, ops only).
OPENROUTER_MODEL_PROBE_CANDIDATES: Tuple[str, ...] = (
    "meta-llama/llama-3.3-8b-instruct:free",
    "mistralai/mistral-7b-instruct:free",
    "qwen/qwen-2.5-7b-instruct",
    "google/gemini-2.0-flash-001",
    "openai/gpt-4o-mini",
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _load_project_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(_repo_root() / ".env")


def _formal_parallel_workers(task_count: int, override: Optional[int] = None) -> int:
    if task_count < 1:
        return 1
    if override is not None:
        return max(1, min(int(override), task_count))
    raw = os.getenv("FORMAL_EVAL_V1_WORKERS", "").strip()
    if raw:
        return max(1, min(int(raw), task_count))
    return max(1, min(4, task_count))


def _minimal_sample_worker(
    sym: str,
    profile: str,
    dates: List[str],
    cfg: Dict[str, Any],
) -> Dict[str, Any]:
    import uuid

    from stockbuddy.evaluation.timeline_backtest import run_timeline_backtest
    from stockbuddy.experiments.timeline import run_pilot_timeline

    bid = f"formal_eval_v1_minimal_{sym}_{profile}_{uuid.uuid4().hex[:8]}"
    r = run_pilot_timeline(
        sym,
        dates,
        cfg,
        selected_analysts=list(FORMAL_EVAL_V1_ANALYSTS),
        pipeline_profile=profile,
        entry="formal_eval_v1_minimal_sample",
        batch_id=bid,
    )
    bt = run_timeline_backtest(
        batch_dir=r.batch_dir, config=formal_eval_v1_merged_config()
    )
    m = json.loads(bt.metrics_path.read_text(encoding="utf-8"))
    return {
        "ticker": sym,
        "profile": profile,
        "batch_dir": str(r.batch_dir),
        "batch_id": r.batch_id,
        "backtest_dir": str(bt.output_dir),
        "metrics": m,
    }


def _full_grid_worker(
    ticker: str,
    profile: str,
    dates: List[str],
    cfg: Dict[str, Any],
    bid: str,
) -> Dict[str, Any]:
    import traceback

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
    }
    try:
        r = run_pilot_timeline(
            ticker,
            dates,
            cfg,
            selected_analysts=list(FORMAL_EVAL_V1_ANALYSTS),
            pipeline_profile=profile,
            entry="formal_eval_v1_grid",
            batch_id=bid,
        )
        row["batch_dir"] = str(r.batch_dir)
        bt = run_timeline_backtest(batch_dir=r.batch_dir, config=cfg)
        row["backtest_dir"] = str(bt.output_dir)
        row["metrics"] = json.loads(bt.metrics_path.read_text(encoding="utf-8"))
        row["status"] = "ok"
    except Exception as exc:
        row["status"] = "failed"
        row["error"] = traceback.format_exc()[-500:]
        print(f"FAILED {ticker} {profile}: {exc}", file=sys.stderr)
    return row


def _assert_live_run_has_no_news_content(run_dir: Path) -> None:
    fs_path = run_dir / "full_state.json"
    if not fs_path.is_file():
        raise RuntimeError(f"missing full_state.json: {run_dir}")
    fs = json.loads(fs_path.read_text(encoding="utf-8"))
    nr = (fs.get("news_report") or "").strip()
    if nr:
        raise RuntimeError("absolute no-news violated: news_report non-empty in full_state")
    nrm = run_dir / "reports" / "news_report.md"
    if nrm.is_file():
        raise RuntimeError("absolute no-news violated: news_report.md exists")


def _period_dates() -> tuple[date, date]:
    a = FORMAL_EVAL_V1_PERIOD_START.split("-")
    b = FORMAL_EVAL_V1_PERIOD_END.split("-")
    return (
        date(int(a[0]), int(a[1]), int(a[2])),
        date(int(b[0]), int(b[1]), int(b[2])),
    )


def _year_months_spanned_by_period(lo: date, hi: date) -> List[Tuple[int, int]]:
    """Inclusive calendar months from lo.month through hi.month (same span as period)."""
    out: List[Tuple[int, int]] = []
    y, m = lo.year, lo.month
    end_y, end_m = hi.year, hi.month
    while (y, m) <= (end_y, end_m):
        out.append((y, m))
        if m == 12:
            y, m = y + 1, 1
        else:
            m += 1
    return out


def compute_monthly_first_trading_days_from_0700() -> List[str]:
    """Recompute dates from 0700.HK; must match FORMAL_EVAL_V1_ANALYSIS_DATES_ISO."""
    lo, hi = _period_dates()
    sym = normalize_hk_symbol("0700")
    df = fetch_ohlc(sym, lo, hi)
    days = trading_days_index(df)
    out: List[str] = []
    for y, month in _year_months_spanned_by_period(lo, hi):
        first: Optional[date] = None
        for d in days:
            if d.year == y and d.month == month:
                first = d
                break
        if first is None:
            raise RuntimeError(
                f"no session in {y}-{month:02d} for calendar proxy 0700.HK"
            )
        out.append(first.isoformat())
    return out


def assert_frozen_dates_match_calendar() -> None:
    got = compute_monthly_first_trading_days_from_0700()
    if got != FORMAL_EVAL_V1_ANALYSIS_DATES_ISO:
        raise AssertionError(
            f"FORMAL_EVAL_V1_ANALYSIS_DATES_ISO out of sync: file={FORMAL_EVAL_V1_ANALYSIS_DATES_ISO} yfinance={got}"
        )


def formal_eval_v1_snapshot() -> Dict[str, Any]:
    return {
        "version": FORMAL_EVAL_V1_VERSION,
        "tickers": list(FORMAL_EVAL_V1_TICKERS),
        "period_start": FORMAL_EVAL_V1_PERIOD_START,
        "period_end": FORMAL_EVAL_V1_PERIOD_END,
        "analysis_dates": list(FORMAL_EVAL_V1_ANALYSIS_DATES_ISO),
        "selected_analysts": list(FORMAL_EVAL_V1_ANALYSTS),
        "profiles": list(FORMAL_EVAL_V1_PROFILES),
        "absolute_no_news": True,
        "memory_disabled": True,
        "calendar_proxy": "0700.HK",
        "fee_schedule": DEFAULT_CONFIG.get("backtest_fee_schedule") or {},
    }


def formal_eval_v1_merged_config(extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Same dict for every ticker × profile; callers set pipeline_profile / ticker only."""
    base: Dict[str, Any] = {
        **DEFAULT_CONFIG,
        "memory_enabled": False,
        "formal_eval_v1": True,
        "formal_eval_v1_snapshot": formal_eval_v1_snapshot(),
    }
    if os.getenv("DEEP_THINK_LLM"):
        base["deep_think_llm"] = os.environ["DEEP_THINK_LLM"]
    if os.getenv("QUICK_THINK_LLM"):
        base["quick_think_llm"] = os.environ["QUICK_THINK_LLM"]
    if extra:
        base.update(extra)
    return base


def assert_full_system_graph_has_no_news_path() -> None:
    """No News/Social analyst nodes => no get_news tool nodes in compiled full_system graph."""
    from stockbuddy.graph.trading_graph import StockBuddyGraph

    if not os.getenv("OPENROUTER_API_KEY") and not os.getenv("OPENAI_API_KEY"):
        os.environ["OPENROUTER_API_KEY"] = "sb-formal-eval-structural-only"

    cfg = formal_eval_v1_merged_config({"pipeline_profile": "full_system"})
    g = StockBuddyGraph(
        selected_analysts=list(FORMAL_EVAL_V1_ANALYSTS),
        config=cfg,
        debug=False,
    )
    nodes = list(g.graph.nodes.keys())
    joined = " ".join(nodes)
    for bad in ("News Analyst", "Social Analyst", "tools_news", "tools_social"):
        if bad in joined:
            raise AssertionError(f"unexpected node in no-news graph: {bad} in {nodes}")


def run_smoke_full_system_one_day_live() -> "PilotTimelineResult":
    """Needs OPENROUTER_API_KEY (or OPENAI for non-openrouter): 1×0700, 1 date, full_system."""
    _load_project_dotenv()
    if not os.getenv("OPENROUTER_API_KEY") and not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError(
            "set OPENROUTER_API_KEY for smoke-live (full_system calls LLM)"
        )

    from stockbuddy.experiments.timeline import run_pilot_timeline

    assert_frozen_dates_match_calendar()

    cfg = formal_eval_v1_merged_config()
    one = [FORMAL_EVAL_V1_ANALYSIS_DATES_ISO[0]]
    r = run_pilot_timeline(
        FORMAL_EVAL_V1_TICKERS[0],
        one,
        cfg,
        selected_analysts=list(FORMAL_EVAL_V1_ANALYSTS),
        pipeline_profile="full_system",
        entry="formal_eval_v1_smoke_live",
    )
    meta = json.loads(r.meta_path.read_text(encoding="utf-8"))
    snap = meta.get("formal_eval_v1")
    if not snap or not snap.get("absolute_no_news"):
        raise RuntimeError("batch_meta missing formal_eval_v1 absolute_no_news")
    if snap.get("selected_analysts") != FORMAL_EVAL_V1_ANALYSTS:
        raise RuntimeError("snapshot analysts mismatch")
    if r.runs:
        _assert_live_run_has_no_news_content(Path(r.runs[0].run_dir))
    return r


def run_minimal_formal_three_profiles(
    *,
    ticker: Optional[str] = None,
    tickers: Optional[List[str]] = None,
    max_workers: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Frozen tickers (default: FORMAL_EVAL_V1_TICKERS) × analysis_dates × three profiles;
    timeline + backtest each. Parallel threads; cap with FORMAL_EVAL_V1_WORKERS (default 4).
    `ticker` alone still means a single-symbol run. Requires API key for LLM profiles.
    """
    _load_project_dotenv()
    if not os.getenv("OPENROUTER_API_KEY") and not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError(
            "set OPENROUTER_API_KEY for minimal-sample (LLM profiles need API)"
        )

    if ticker is not None:
        syms: List[str] = [ticker]
    elif tickers is not None:
        syms = list(tickers)
    else:
        syms = list(FORMAL_EVAL_V1_TICKERS)

    dates = list(FORMAL_EVAL_V1_ANALYSIS_DATES_ISO)
    cfg = formal_eval_v1_merged_config()
    tasks = [(s, p) for s in syms for p in FORMAL_EVAL_V1_PROFILES]
    nw = _formal_parallel_workers(len(tasks), max_workers)
    out: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=nw) as ex:
        futs = [ex.submit(_minimal_sample_worker, s, p, dates, cfg) for s, p in tasks]
        for fu in futs:
            out.append(fu.result())
    out.sort(
        key=lambda r: (
            _TICKER_ORDER.get(r["ticker"], 99),
            _PROFILE_ORDER[r["profile"]],
        )
    )
    return out


def _classify_provider_error(exc: BaseException) -> Tuple[str, str]:
    """(bucket, detail_truncated); bucket: none|403|404|other."""
    msg = str(exc)
    code = getattr(exc, "status_code", None)
    if code == 403:
        return "403", msg[:400]
    if code == 404:
        return "404", msg[:400]
    low = msg.lower()
    if "403" in msg or "forbidden" in low or "not available in your region" in low:
        return "403", msg[:400]
    if "404" in msg or "not found" in low and "endpoint" in low:
        return "404", msg[:400]
    return "other", msg[:400]


def probe_openrouter_models_minimal() -> List[Dict[str, Any]]:
    """
    One short chat completion per model; same transport as StockBuddy (OpenRouter).
    Does not change formal_eval_v1 constants.
    """
    _load_project_dotenv()
    if not os.getenv("OPENROUTER_API_KEY"):
        raise RuntimeError("OPENROUTER_API_KEY required for model-check")

    from langchain_core.messages import HumanMessage
    from langchain_openai import ChatOpenAI

    backend = os.getenv("BACKEND_URL", DEFAULT_CONFIG["backend_url"])
    headers = {
        "HTTP-Referer": "https://github.com/KarenShark/StockBuddy_Latest-v4",
        "X-Title": "StockBuddy",
    }
    out: List[Dict[str, Any]] = []
    for model in OPENROUTER_MODEL_PROBE_CANDIDATES:
        row: Dict[str, Any] = {
            "model": model,
            "ok": False,
            "error_bucket": "",
            "detail": "",
            "suitable_formal_eval_v1": False,
        }
        try:
            llm = ChatOpenAI(
                model=model,
                base_url=backend,
                api_key=os.environ["OPENROUTER_API_KEY"],
                default_headers=headers,
                max_tokens=32,
                timeout=90,
            )
            r = llm.invoke([HumanMessage(content="Reply exactly: OK")])
            text = (getattr(r, "content", None) or "").strip()
            row["ok"] = bool(text)
            row["error_bucket"] = "none"
            row["detail"] = text[:80] if text else "(empty content)"
            row["suitable_formal_eval_v1"] = bool(text)
        except BaseException as e:
            bucket, detail = _classify_provider_error(e)
            row["error_bucket"] = bucket
            row["detail"] = detail
            row["suitable_formal_eval_v1"] = False
        out.append(row)
    return out


def format_model_probe_table(rows: List[Dict[str, Any]]) -> str:
    lines = [
        "| model | ok | error | suitable formal_eval_v1 |",
        "| --- | --- | --- | --- |",
    ]
    for row in rows:
        if row.get("error_bucket") == "none":
            err_cell = "—"
        else:
            b = row.get("error_bucket", "other")
            d = (row.get("detail") or "").replace("|", "/").replace("\n", " ")[:120]
            err_cell = f"{b}: {d}" if d else b
        lines.append(
            f"| {row['model']} | {row['ok']} | {err_cell} | {row['suitable_formal_eval_v1']} |"
        )
    return "\n".join(lines)


def format_minimal_sample_table(rows: List[Dict[str, Any]]) -> str:
    lines = [
        "| ticker | profile | buy/sell/hold/null | num_trades | final_equity | total_return | max_drawdown | num_signals_ignored_by_protocol |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    ordered = sorted(
        rows,
        key=lambda r: (
            _TICKER_ORDER.get(r.get("ticker", ""), 99),
            _PROFILE_ORDER[r["profile"]],
        ),
    )
    for row in ordered:
        m = row["metrics"]
        dist = f"{m.get('num_buy_signals')}/{m.get('num_sell_signals')}/{m.get('num_hold_signals')}/{m.get('num_null_or_other_signals')}"
        tk = row.get("ticker", "—")
        lines.append(
            f"| {tk} | {row['profile']} | {dist} | {m.get('num_trades')} | {m.get('final_equity'):.4f} | {m.get('total_return'):.6f} | {m.get('max_drawdown'):.6f} | {m.get('num_signals_ignored_by_protocol')} |"
        )
    return "\n".join(lines)


def run_full_formal_grid(*, max_workers: Optional[int] = None) -> List[Dict[str, Any]]:
    """3 tickers × 3 profiles; parallel; same worker cap as minimal-sample."""
    import uuid

    _load_project_dotenv()
    if not os.getenv("OPENROUTER_API_KEY") and not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("set OPENROUTER_API_KEY for full-grid")

    dates = list(FORMAL_EVAL_V1_ANALYSIS_DATES_ISO)
    cfg = formal_eval_v1_merged_config()
    tasks: List[Tuple[str, str, str]] = []
    for ticker in FORMAL_EVAL_V1_TICKERS:
        for profile in FORMAL_EVAL_V1_PROFILES:
            bid = f"formal_v1_{ticker}_{profile}_{uuid.uuid4().hex[:6]}"
            tasks.append((ticker, profile, bid))

    nw = _formal_parallel_workers(len(tasks), max_workers)
    out: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=nw) as ex:
        futs = [
            ex.submit(_full_grid_worker, t, p, dates, cfg, bid)
            for t, p, bid in tasks
        ]
        for fu in futs:
            out.append(fu.result())
    return out


def format_full_grid_table(rows: List[Dict[str, Any]]) -> str:
    lines = [
        "| ticker | profile | B/S/H/null | trades | final_equity | return | max_dd | win_rate | ignored | status |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        m = row.get("metrics")
        if m:
            dist = f"{m.get('num_buy_signals',0)}/{m.get('num_sell_signals',0)}/{m.get('num_hold_signals',0)}/{m.get('num_null_or_other_signals',0)}"
            wr = m.get("win_rate")
            wrs = f"{wr:.4f}" if wr is not None else "—"
            lines.append(
                f"| {row['ticker']} | {row['profile']} | {dist} | {m.get('num_trades',0)} "
                f"| {m.get('final_equity',0):.2f} | {m.get('total_return',0)*100:.2f}% "
                f"| {m.get('max_drawdown',0)*100:.2f}% | {wrs} | {m.get('num_signals_ignored_by_protocol',0)} "
                f"| {row['status']} |"
            )
        else:
            lines.append(
                f"| {row['ticker']} | {row['profile']} | — | — | — | — | — | — | — | {row['status']} |"
            )
    return "\n".join(lines)


def format_cross_ticker_summary(rows: List[Dict[str, Any]]) -> str:
    from collections import defaultdict
    by_profile: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("metrics"):
            by_profile[row["profile"]].append(row["metrics"])

    lines = [
        "| profile | n_tickers | avg_return | avg_max_dd | avg_trades | return_range |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for prof in FORMAL_EVAL_V1_PROFILES:
        ms = by_profile.get(prof, [])
        if not ms:
            lines.append(f"| {prof} | 0 | — | — | — | — |")
            continue
        rets = [m["total_return"] for m in ms]
        dds = [m["max_drawdown"] for m in ms]
        trs = [m["num_trades"] for m in ms]
        avg_r = sum(rets) / len(rets)
        avg_d = sum(dds) / len(dds)
        avg_t = sum(trs) / len(trs)
        rng = f"[{min(rets)*100:.2f}%, {max(rets)*100:.2f}%]"
        lines.append(
            f"| {prof} | {len(ms)} | {avg_r*100:.2f}% | {avg_d*100:.2f}% | {avg_t:.1f} | {rng} |"
        )
    return "\n".join(lines)


def run_smoke_default() -> None:
    """Frozen dates + compiled graph excludes news/social (no LLM, no API key)."""
    assert_frozen_dates_match_calendar()
    assert_full_system_graph_has_no_news_path()


def run_lineage_gate_smoke() -> None:
    """Writes a temp run dir; mocks LLM enrichment so G1 fires on synthetic BUY."""
    import tempfile
    from datetime import datetime, timezone
    from unittest.mock import patch

    from stockbuddy.experiments.artifacts import new_run_id, write_experiment_bundle

    run_id = new_run_id()
    tmp = Path(tempfile.mkdtemp())
    final_state: Dict[str, Any] = {
        "final_trade_decision": "Recommendation: BUY.",
        "market_report": "# Market\nlineage-smoke",
        "trader_investment_plan": "Neutral.",
        "risk_debate_state": {"judge_decision": "OK"},
    }
    fake_enr = {
        "rationale_summary": "smoke",
        "confidence": 0.35,
        "risk_flags": [],
        "no_trade_reason": None,
        "enrichment_mode": "llm",
        "enrichment_error": None,
    }
    cfg = {**DEFAULT_CONFIG, "pipeline_profile": "single_agent"}
    started = datetime.now(timezone.utc).isoformat()
    with patch(
        "stockbuddy.experiments.artifacts.enrich_decision_fields",
        return_value=fake_enr,
    ):
        write_experiment_bundle(
            run_dir=tmp,
            run_id=run_id,
            ticker="0700",
            analysis_date="2024-06-03",
            final_state=final_state,
            signal_str="BUY\n",
            config=cfg,
            entry="lineage-smoke",
            started_at=started,
            finished_at=started,
        )

    dec = json.loads((tmp / "decision.json").read_text(encoding="utf-8"))
    lin = json.loads((tmp / "lineage.json").read_text(encoding="utf-8"))
    assert dec.get("gate_triggers") == ["G1"], dec.get("gate_triggers")
    assert "G1" in (dec.get("gate_evidence") or {}), dec.get("gate_evidence")
    assert dec.get("parsed_action_pre_gate") == "BUY"
    assert dec.get("parsed_action_post_gate") == "HOLD"
    assert dec.get("action") == "HOLD"
    for k in (
        "report_paths",
        "signal_raw",
        "parsed_action_pre_gate",
        "parsed_action_post_gate",
        "gate_summary",
        "order_spec_path",
    ):
        assert k in lin, f"missing lineage key {k}"
    assert lin.get("order_spec_path") == "order_spec.json"
    print("OK lineage-gate-smoke run_dir=", tmp)
    print("decision gate_triggers=", dec.get("gate_triggers"))
    print("lineage gate_summary=", lin.get("gate_summary"))


def run_news_smoke(ticker: str = "0700", analysis_date: str = "2024-06-03") -> str:
    """Single-ticker single-date Google RSS path; 7d lookback ending on analysis_date."""
    from datetime import datetime, timedelta

    from stockbuddy.dataflows.google import get_google_news

    d = datetime.strptime(analysis_date, "%Y-%m-%d").date()
    start = (d - timedelta(days=7)).isoformat()
    end = analysis_date
    out = get_google_news(ticker, start, end)
    line0 = out.split("\n", 1)[0].strip()
    if not line0.startswith("STOCKBUDDY_NEWS_JSON:"):
        raise RuntimeError(f"missing STOCKBUDDY_NEWS_JSON header: {line0[:120]!r}")
    meta = json.loads(line0.split(":", 1)[1])
    st = meta.get("status")
    if st not in ("ok", "empty_window", "provider_error", "parse_error"):
        raise RuntimeError(f"unexpected news meta status: {meta!r}")
    print(line0)
    preview = out[len(line0) :].strip()[:400]
    if preview:
        print("--- body preview ---")
        print(preview)
    print(f"PASSED news-smoke status={st}")
    return str(st)


def main(argv: Optional[List[str]] = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if argv and argv[0] == "smoke":
        run_smoke_default()
        print(
            "OK formal_eval_v1 smoke (dates + full_system graph has no news/social nodes)"
        )
        return 0
    if argv and argv[0] == "smoke-live":
        r = run_smoke_full_system_one_day_live()
        print("batch_dir:", r.batch_dir)
        print(
            "OK formal_eval_v1 smoke-live (full_system timeline, batch_meta no-news snapshot)"
        )
        return 0
    if argv and argv[0] == "minimal-sample":
        rows = run_minimal_formal_three_profiles()
        print(format_minimal_sample_table(rows))
        for row in rows:
            print(
                "batch_dir",
                f"{row.get('ticker', '')} {row['profile']}:",
                row["batch_dir"],
            )
        if len({r.get("ticker") for r in rows}) > 1:
            print("\n--- Cross-ticker summary ---")
            print(format_cross_ticker_summary(rows))
        man: Dict[str, Any] = {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "universe": list(FORMAL_EVAL_V1_TICKERS),
            "protocol_note": "same 3-month window + analysis_dates as formal_eval_v1; baseline backtest hold=5 sessions",
            "cells": [],
        }
        for row in rows:
            mp = Path(row["backtest_dir"]) / "metrics.json"
            cell: Dict[str, Any] = {
                "ticker": row["ticker"],
                "profile": row["profile"],
                "batch_dir": row["batch_dir"],
                "backtest_dir": row["backtest_dir"],
                "metrics_path": str(mp.resolve()),
            }
            if mp.is_file():
                m = json.loads(mp.read_text(encoding="utf-8"))
                cell["baseline_5d"] = {
                    k: m.get(k)
                    for k in (
                        "symbol",
                        "total_return",
                        "num_trades",
                        "max_drawdown",
                        "num_buy_signals",
                        "num_sell_signals",
                        "num_hold_signals",
                        "num_signals_ignored_by_protocol",
                    )
                }
            man["cells"].append(cell)
        man_path = _repo_root() / "experiments" / "preliminary_results" / "last_minimal_run_manifest.json"
        man_path.parent.mkdir(parents=True, exist_ok=True)
        man_path.write_text(json.dumps(man, ensure_ascii=False, indent=2), encoding="utf-8")
        print("manifest:", man_path)
        return 0
    if argv and argv[0] == "full-grid":
        all_rows = run_full_formal_grid()
        print(format_full_grid_table(all_rows))
        print("\n--- Cross-ticker summary ---")
        print(format_cross_ticker_summary(all_rows))
        for row in all_rows:
            print(f"  {row['ticker']} {row['profile']}: {row.get('status')} batch={row.get('batch_dir','N/A')}")
        return 0
    if argv and argv[0] == "verify-dates":
        assert_frozen_dates_match_calendar()
        print("OK frozen dates match 0700.HK calendar")
        return 0
    if argv and argv[0] == "model-check":
        rows = probe_openrouter_models_minimal()
        print(format_model_probe_table(rows))
        first = next((r["model"] for r in rows if r.get("suitable_formal_eval_v1")), None)
        if first:
            print(f"\nfirst_suitable_model={first}")
            print(
                f"DEEP_THINK_LLM={first} QUICK_THINK_LLM={first} "
                "python3 -m stockbuddy.experiments.formal_eval_v1 minimal-sample"
            )
        else:
            print("\nfirst_suitable_model=(none)")
        return 0
    if argv and argv[0] == "news-smoke":
        t = argv[1] if len(argv) > 1 else "0700"
        ad = argv[2] if len(argv) > 2 else "2024-06-03"
        run_news_smoke(t, ad)
        return 0
    if argv and argv[0] == "lineage-smoke":
        run_lineage_gate_smoke()
        return 0
    print(
        "usage: python -m stockbuddy.experiments.formal_eval_v1 "
        "verify-dates|smoke|smoke-live|model-check|minimal-sample|full-grid|"
        "news-smoke|lineage-smoke\n"
        "optional: FORMAL_EVAL_V1_WORKERS=N (parallel cap for minimal-sample/full-grid)",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
