"""
Reusable experiment artifacts: decision.json v1, full_state, config snapshot, reports.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from stockbuddy.experiments.asset_infer import infer_asset_type
from stockbuddy.experiments.enrichment import enrich_decision_fields
from stockbuddy.experiments.order_spec import generate_order_spec_from_decision
from stockbuddy.graph.signal_vocab import (
    BUY_SIDE_ACTIONS,
    action_to_direction_score,
    parse_action_from_signal,
)

DECISION_SCHEMA_VERSION = "1.3"

# Keys written as reports/<key>.md (aligned with main.py legacy list)
REPORT_SECTION_KEYS = [
    "market_report",
    "sentiment_report",
    "news_report",
    "fundamentals_report",
    "investment_plan",
    "trader_investment_plan",
    "final_trade_decision",
]

_SENSITIVE_KEY_RE = re.compile(r"(api[_-]?key|secret|password|token|credential)", re.I)


def new_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:12]


def experiments_root_path(config: Dict[str, Any]) -> Path:
    raw = config.get("experiments_dir", "experiments")
    p = Path(raw).expanduser()
    return p.resolve() if p.is_absolute() else (Path.cwd() / p).resolve()


def sanitize_config(config: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k, v in config.items():
        if isinstance(k, str) and _SENSITIVE_KEY_RE.search(k):
            out[k] = "***set***" if v else None
        elif isinstance(v, dict):
            out[k] = sanitize_config(v)
        else:
            out[k] = v
    return out


def get_git_commit() -> Optional[str]:
    try:
        root = Path(__file__).resolve().parents[2]
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if out.returncode == 0 and out.stdout:
            return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def _inv_state(s: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "bull_history": s.get("bull_history", ""),
        "bear_history": s.get("bear_history", ""),
        "history": s.get("history", ""),
        "current_response": s.get("current_response", ""),
        "judge_decision": s.get("judge_decision", ""),
    }


def _risk_state(s: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "risky_history": s.get("risky_history", ""),
        "safe_history": s.get("safe_history", ""),
        "neutral_history": s.get("neutral_history", ""),
        "history": s.get("history", ""),
        "judge_decision": s.get("judge_decision", ""),
    }


def build_full_state_dict(final_state: Dict[str, Any]) -> Dict[str, Any]:
    """Single-run snapshot; fields align with trading_graph._log_state per-date."""
    inv = final_state.get("investment_debate_state") or {}
    risk = final_state.get("risk_debate_state") or {}
    return {
        "company_of_interest": final_state.get("company_of_interest", ""),
        "trade_date": final_state.get("trade_date", ""),
        "market_report": final_state.get("market_report", ""),
        "sentiment_report": final_state.get("sentiment_report", ""),
        "news_report": final_state.get("news_report", ""),
        "fundamentals_report": final_state.get("fundamentals_report", ""),
        "investment_debate_state": _inv_state(inv if isinstance(inv, dict) else {}),
        "trader_investment_decision": final_state.get("trader_investment_plan", ""),
        "risk_debate_state": _risk_state(risk if isinstance(risk, dict) else {}),
        "investment_plan": final_state.get("investment_plan", ""),
        "final_trade_decision": final_state.get("final_trade_decision", ""),
    }


def evaluate_buy_risk_gates(
    *,
    parsed_action_pre: Optional[str],
    confidence: Optional[float],
    risk_flags: List[str],
    final_state: Dict[str, Any],
    pipeline_profile: Optional[str],
) -> Dict[str, Any]:
    """
    Deterministic buy-side-only guardrail (BUY or OVERWEIGHT).
    Purpose: reduce high-risk / impulsive new longs when signal is already bullish.
    G1/G2: numeric / count thresholds. G3/G4: rule-based substring conflict
    detector on agent text (not semantic NLU; false positives possible).
    First match wins (legacy elif chain).
    """
    triggers: List[str] = []
    evidence: Dict[str, Any] = {}

    if parsed_action_pre not in BUY_SIDE_ACTIONS:
        return {
            "gate_triggers": [],
            "gate_evidence": {},
            "blocked_by_risk_gate": False,
            "gate_reason": None,
            "parsed_action_post": parsed_action_pre,
            "gate_summary": (
                "gates_skipped_non_buy_side"
                if parsed_action_pre
                else "gates_skipped_no_parsed_action"
            ),
        }

    if confidence is not None and confidence < 0.6:
        triggers.append("G1")
        evidence["G1"] = {
            "rule": "confidence_buy_minimum",
            "confidence": confidence,
            "threshold": 0.6,
        }
        return {
            "gate_triggers": triggers,
            "gate_evidence": evidence,
            "blocked_by_risk_gate": True,
            "gate_reason": f"G1: confidence {confidence} < 0.6",
            "parsed_action_post": "HOLD",
            "gate_summary": f"blocked_by_G1_low_confidence({confidence})",
        }

    if len(risk_flags) >= 3:
        triggers.append("G2")
        evidence["G2"] = {
            "rule": "risk_flags_count",
            "count": len(risk_flags),
            "threshold": 3,
            "sample": risk_flags[:5],
        }
        return {
            "gate_triggers": triggers,
            "gate_evidence": evidence,
            "blocked_by_risk_gate": True,
            "gate_reason": f"G2: {len(risk_flags)} risk_flags >= 3",
            "parsed_action_post": "HOLD",
            "gate_summary": f"blocked_by_G2_risk_flags(n={len(risk_flags)})",
        }

    if final_state:
        # G3/G4: keyword guardrails only; do not treat as strict meaning extraction.
        trader_plan = str(final_state.get("trader_investment_plan") or "").lower()
        if "sell" in trader_plan or "看空" in trader_plan or "賣出" in trader_plan:
            triggers.append("G3")
            evidence["G3"] = {
                "rule": "trader_sell_vs_final_buy",
                "trader_snippet": (final_state.get("trader_investment_plan") or "")[:240],
            }
            return {
                "gate_triggers": triggers,
                "gate_evidence": evidence,
                "blocked_by_risk_gate": True,
                "gate_reason": "G3: trader SELL/bearish vs final BUY",
                "parsed_action_post": "HOLD",
                "gate_summary": "blocked_by_G3_trader_disagreement",
            }

        if pipeline_profile != "single_agent":
            risk_judge = str(
                (final_state.get("risk_debate_state") or {}).get("judge_decision", "")
            ).lower()
            if (
                "sell" in risk_judge
                or "hold" in risk_judge
                or "看空" in risk_judge
                or "觀望" in risk_judge
            ):
                triggers.append("G4")
                evidence["G4"] = {
                    "rule": "risk_judge_non_buy_vs_final_buy",
                    "judge_snippet": str(
                        (final_state.get("risk_debate_state") or {}).get(
                            "judge_decision", ""
                        )
                    )[:240],
                }
                return {
                    "gate_triggers": triggers,
                    "gate_evidence": evidence,
                    "blocked_by_risk_gate": True,
                    "gate_reason": "G4: risk judge non-BUY vs final BUY",
                    "parsed_action_post": "HOLD",
                    "gate_summary": "blocked_by_G4_risk_judge_disagreement",
                }

    return {
        "gate_triggers": [],
        "gate_evidence": {},
        "blocked_by_risk_gate": False,
        "gate_reason": None,
        "parsed_action_post": parsed_action_pre,
        "gate_summary": "passed_G1_G4_buy_side_allowed",
    }


def build_lineage_record(
    *,
    run_id: str,
    decision: Dict[str, Any],
    report_keys: List[str],
    order_spec_written: bool,
) -> Dict[str, Any]:
    """Decision-chain summary for audit; not a full provenance graph."""
    paths = {k: f"reports/{k}.md" for k in report_keys}
    return {
        "schema_version": "1.0",
        "run_id": run_id,
        "report_paths": paths,
        "signal_raw": decision.get("signal_raw"),
        "parsed_action_pre_gate": decision.get("parsed_action_pre_gate"),
        "parsed_action_post_gate": decision.get("parsed_action_post_gate"),
        "gate_triggers": decision.get("gate_triggers"),
        "gate_evidence": decision.get("gate_evidence"),
        "gate_summary": decision.get("gate_summary"),
        "order_spec_path": "order_spec.json" if order_spec_written else None,
    }


def infer_news_status(final_state: Dict[str, Any]) -> str:
    """
    Decision-layer news_status (not graph-internal):
    skipped | ok | empty_window | provider_error | parse_error
    """
    nr = (final_state.get("news_report") or "").strip()
    if not nr:
        return "skipped"
    first = nr.split("\n", 1)[0].strip()
    if first.startswith("STOCKBUDDY_NEWS_JSON:"):
        try:
            meta = json.loads(first.split(":", 1)[1])
            st = meta.get("status")
            if st in (
                "ok",
                "empty_window",
                "provider_error",
                "parse_error",
            ):
                return str(st)
            return "parse_error"
        except json.JSONDecodeError:
            return "parse_error"
    if "Company news: unavailable" in nr:
        return "empty_window"
    if "google_news_empty" in nr or "no articles in date window" in nr.lower():
        return "empty_window"
    return "ok"


def build_decision_record(
    *,
    run_id: str,
    ticker: str,
    analysis_date: str,
    final_state: Dict[str, Any],
    signal_str: str,
    config: Dict[str, Any],
) -> Dict[str, Any]:
    action = parse_action_from_signal(signal_str)
    asset_type, asset_type_source = infer_asset_type(ticker, config)
    enr = enrich_decision_fields(config, final_state, signal_str, action)

    mode = enr.get("enrichment_mode", "heuristic")
    confidence: Optional[float] = None
    if mode == "llm":
        c = enr.get("confidence")
        if isinstance(c, (int, float)) and 0.0 <= float(c) <= 1.0:
            confidence = float(c)

    no_trade_reason: Optional[str] = enr.get("no_trade_reason")
    if no_trade_reason is None and action is None:
        no_trade_reason = "signal_unparsed"

    err = enr.get("enrichment_error")
    enrichment_block = {
        "mode": mode,
        "model": config.get("quick_think_llm") if mode == "llm" else None,
        "error": err if err else None,
    }

    profile = config.get("pipeline_profile")
    signal_source = (
        "single_agent" if profile == "single_agent" else "signal_processor"
    )

    risk_flags = list(enr.get("risk_flags") or [])
    parsed_pre = action

    gates_enabled = config.get("risk_gates_enabled", True)
    if gates_enabled:
        gate_out = evaluate_buy_risk_gates(
            parsed_action_pre=parsed_pre,
            confidence=confidence,
            risk_flags=risk_flags,
            final_state=final_state,
            pipeline_profile=profile,
        )
    else:
        gate_out = {
            "gate_triggers": [],
            "gate_evidence": {},
            "blocked_by_risk_gate": False,
            "gate_reason": None,
            "parsed_action_post": parsed_pre,
            "gate_summary": "gates_disabled_by_config",
        }
    blocked_by_risk_gate = bool(gate_out["blocked_by_risk_gate"])
    gate_reason = gate_out.get("gate_reason")
    gate_triggers: List[str] = list(gate_out.get("gate_triggers") or [])
    gate_evidence: Dict[str, Any] = dict(gate_out.get("gate_evidence") or {})
    gate_summary = str(gate_out.get("gate_summary") or "")
    parsed_post: Optional[str] = gate_out.get("parsed_action_post")  # type: ignore[assignment]

    action = parsed_post if parsed_post is not None else parsed_pre
    if blocked_by_risk_gate:
        no_trade_reason = "blocked_by_risk_gate"

    return {
        "schema_version": DECISION_SCHEMA_VERSION,
        "run_id": run_id,
        "ticker": ticker,
        "analysis_date": analysis_date,
        "asset_type": asset_type,
        "asset_type_source": asset_type_source,
        "action": action,
        "direction_score": action_to_direction_score(action),
        "confidence": confidence,
        "risk_flags": risk_flags,
        "no_trade_reason": no_trade_reason,
        "blocked_by_risk_gate": blocked_by_risk_gate,
        "gate_reason": gate_reason,
        "gate_triggers": gate_triggers,
        "gate_evidence": gate_evidence,
        "parsed_action_pre_gate": parsed_pre,
        "parsed_action_post_gate": action,
        "gate_summary": gate_summary,
        "rationale_summary": enr.get("rationale_summary"),
        "signal_raw": signal_str,
        "signal_source": signal_source,
        "enrichment": enrichment_block,
        "news_status": infer_news_status(final_state),
        "get_news_vendor": (config.get("tool_vendors") or {}).get("get_news"),
    }


def build_buy_and_hold_decision_record(
    *,
    run_id: str,
    ticker: str,
    analysis_date: str,
    config: Dict[str, Any],
    is_first_timeline_date: bool,
) -> Dict[str, Any]:
    # First row in analysis_dates order: BUY; rest: HOLD (long-only: no new entries).
    asset_type, asset_type_source = infer_asset_type(ticker, config)
    if is_first_timeline_date:
        signal_str = "BUY"
        action: Optional[str] = "BUY"
    else:
        signal_str = "HOLD"
        action = "HOLD"
    return {
        "schema_version": DECISION_SCHEMA_VERSION,
        "run_id": run_id,
        "ticker": ticker,
        "analysis_date": analysis_date,
        "asset_type": asset_type,
        "asset_type_source": asset_type_source,
        "action": action,
        "direction_score": action_to_direction_score(action),
        "confidence": None,
        "risk_flags": [],
        "no_trade_reason": None,
        "blocked_by_risk_gate": False,
        "gate_reason": None,
        "gate_triggers": [],
        "gate_evidence": {},
        "parsed_action_pre_gate": action,
        "parsed_action_post_gate": action,
        "gate_summary": "buy_and_hold_no_risk_gates",
        "rationale_summary": (
            "Phase1 buy-and-hold: single entry on first timeline date, HOLD thereafter."
        ),
        "signal_raw": signal_str,
        "signal_source": "buy_and_hold",
        "enrichment": {"mode": "deterministic", "model": None, "error": None},
        "news_status": "skipped",
        "get_news_vendor": None,
    }


def write_buy_and_hold_experiment_bundle(
    *,
    run_dir: Path,
    run_id: str,
    ticker: str,
    analysis_date: str,
    config: Dict[str, Any],
    entry: str,
    started_at: str,
    finished_at: str,
    is_first_timeline_date: bool,
) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    reports_dir = run_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    final_state: Dict[str, Any] = {}
    written_keys = write_report_md_files(reports_dir, final_state)

    decision = build_buy_and_hold_decision_record(
        run_id=run_id,
        ticker=ticker,
        analysis_date=analysis_date,
        config=config,
        is_first_timeline_date=is_first_timeline_date,
    )
    full_state = build_full_state_dict(final_state)
    order_spec = generate_order_spec_from_decision(decision)
    (run_dir / "full_state.json").write_text(
        json.dumps(full_state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (run_dir / "decision.json").write_text(
        json.dumps(decision, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    order_spec_written = False
    if order_spec:
        (run_dir / "order_spec.json").write_text(
            json.dumps(order_spec, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        order_spec_written = True
    _write_lineage_json(
        run_dir,
        run_id=run_id,
        decision=decision,
        report_keys=written_keys,
        order_spec_written=order_spec_written,
    )
    (run_dir / "config_snapshot.json").write_text(
        json.dumps(sanitize_config(dict(config)), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    meta = {
        "run_id": run_id,
        "entry": entry,
        "ticker": ticker,
        "analysis_date": analysis_date,
        "started_at": started_at,
        "finished_at": finished_at,
        "git_commit": get_git_commit(),
        "python": sys.version.split()[0],
        "platform": sys.platform,
        "pipeline_profile": "buy_and_hold",
        "news_status": decision.get("news_status"),
        "get_news_vendor": decision.get("get_news_vendor"),
    }
    (run_dir / "run_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_summary_md(
        run_dir / "summary.md",
        run_id=run_id,
        ticker=ticker,
        analysis_date=analysis_date,
        decision=decision,
        report_keys=written_keys,
    )


def _write_lineage_json(
    run_dir: Path,
    *,
    run_id: str,
    decision: Dict[str, Any],
    report_keys: List[str],
    order_spec_written: bool,
) -> None:
    rec = build_lineage_record(
        run_id=run_id,
        decision=decision,
        report_keys=report_keys,
        order_spec_written=order_spec_written,
    )
    (run_dir / "lineage.json").write_text(
        json.dumps(rec, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_report_md_files(report_dir: Path, final_state: Dict[str, Any]) -> List[str]:
    report_dir.mkdir(parents=True, exist_ok=True)
    written: List[str] = []
    for key in REPORT_SECTION_KEYS:
        if key in final_state and final_state[key]:
            p = report_dir / f"{key}.md"
            p.write_text(str(final_state[key]), encoding="utf-8")
            written.append(key)
    return written


def write_summary_md(
    path: Path,
    *,
    run_id: str,
    ticker: str,
    analysis_date: str,
    decision: Dict[str, Any],
    report_keys: List[str],
) -> None:
    lines = [
        f"# Run {run_id}",
        "",
        f"- **ticker**: {ticker}",
        f"- **analysis_date**: {analysis_date}",
        f"- **action**: {decision.get('action')}",
        f"- **asset_type**: {decision.get('asset_type')}",
        f"- **confidence**: {decision.get('confidence')}",
        f"- **schema**: decision.json v{decision.get('schema_version')}",
        "",
        "## Reports",
        "",
    ]
    for k in report_keys:
        lines.append(f"- `{k}.md`")
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "Artifacts: `decision.json`, `lineage.json`, `full_state.json`, `config_snapshot.json`, `run_meta.json`.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def write_experiment_bundle(
    *,
    run_dir: Path,
    run_id: str,
    ticker: str,
    analysis_date: str,
    final_state: Dict[str, Any],
    signal_str: str,
    config: Dict[str, Any],
    entry: str,
    started_at: str,
    finished_at: str,
) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    reports_dir = run_dir / "reports"
    written_keys = write_report_md_files(reports_dir, final_state)

    decision = build_decision_record(
        run_id=run_id,
        ticker=ticker,
        analysis_date=analysis_date,
        final_state=final_state,
        signal_str=signal_str,
        config=config,
    )

    full_state = build_full_state_dict(final_state)
    order_spec = generate_order_spec_from_decision(decision)

    (run_dir / "full_state.json").write_text(
        json.dumps(full_state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (run_dir / "decision.json").write_text(
        json.dumps(decision, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    order_spec_written = False
    if order_spec:
        (run_dir / "order_spec.json").write_text(
            json.dumps(order_spec, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        order_spec_written = True
    _write_lineage_json(
        run_dir,
        run_id=run_id,
        decision=decision,
        report_keys=written_keys,
        order_spec_written=order_spec_written,
    )
    (run_dir / "config_snapshot.json").write_text(
        json.dumps(sanitize_config(dict(config)), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    meta = {
        "run_id": run_id,
        "entry": entry,
        "ticker": ticker,
        "analysis_date": analysis_date,
        "started_at": started_at,
        "finished_at": finished_at,
        "git_commit": get_git_commit(),
        "python": sys.version.split()[0],
        "platform": sys.platform,
        "news_status": decision.get("news_status"),
        "get_news_vendor": decision.get("get_news_vendor"),
    }
    (run_dir / "run_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    write_summary_md(
        run_dir / "summary.md",
        run_id=run_id,
        ticker=ticker,
        analysis_date=analysis_date,
        decision=decision,
        report_keys=written_keys,
    )
